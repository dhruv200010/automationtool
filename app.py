import os
import sys
import json
import subprocess
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string, render_template, send_from_directory, redirect, url_for
import logging
from celery_app import celery_app, process_video_task, cleanup_task, auto_cleanup_task

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_pipeline_logs():
    """Clear pipeline logs before processing a new video"""
    try:
        log_file = Path('pipeline.log')
        if log_file.exists():
            log_file.unlink()
            logger.info("🗑️ Cleared previous pipeline logs")
    except Exception as e:
        logger.warning(f"⚠️ Could not clear logs: {str(e)}")

def get_config_paths():
    """Get input and output paths from config file"""
    try:
        config_path = Path(__file__).parent / "config" / "master_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        input_folder = config.get('input_folder', './input')
        output_folder = config.get('output_folder', './output')
        
        # Use Hostinger KVM 2 paths
        input_folder = '/opt/video-automation/input'
        output_folder = '/opt/video-automation/output'
        logger.info("🖥️ Running on Hostinger KVM 2 - using Hostinger paths")
        
        return input_folder, output_folder
    except Exception as e:
        logger.warning(f"⚠️ Could not read config, using default paths: {str(e)}")
        # Use Hostinger KVM 2 default paths
        return '/opt/video-automation/input', '/opt/video-automation/output'

def validate_environment():
    """Validate that required environment variables and dependencies are available"""
    logger.info("🔍 Validating environment...")
    
    # Check for required environment variables
    required_env_vars = ['PORT']
    missing_vars = []
    
    for var in required_env_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"⚠️ Missing environment variables: {missing_vars}")
    
    # Get paths from config
    input_folder, output_folder = get_config_paths()
    required_dirs = [input_folder, output_folder]
    
    for dir_path in required_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Directory ready: {dir_path}")
    
    # Check for ffmpeg availability
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logger.info("✅ ffmpeg is available")
        else:
            logger.error("❌ ffmpeg not working properly")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.error("❌ ffmpeg not found - this will cause pipeline failures")
    
    # Check for Python dependencies
    try:
        import openai
        logger.info("✅ OpenAI library available")
    except ImportError:
        logger.warning("⚠️ OpenAI library not found")
    
    logger.info("🔍 Environment validation complete")

# HTML template for file upload with async processing
UPLOAD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Video Automation Pipeline</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; }
        .upload-area:hover { border-color: #999; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background: #0056b3; }
        button:disabled { background: #6c757d; cursor: not-allowed; }
        .status { margin: 20px 0; padding: 10px; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        .warning { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
        .progress-bar { width: 100%; height: 20px; background-color: #f0f0f0; border-radius: 10px; overflow: hidden; margin: 10px 0; }
        .progress-fill { height: 100%; background-color: #007bff; width: 0%; transition: width 0.3s ease; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #007bff; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; display: inline-block; margin-right: 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .hidden { display: none; }
        .task-info { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>🎬 Video Automation Pipeline</h1>
    <p>Upload a video file to process it through the automation pipeline.</p>
    
    <form id="uploadForm" enctype="multipart/form-data">
        <div class="upload-area">
            <input type="file" name="file" accept=".mp4,.mov,.avi,.mkv" required>
            <p>Select a video file (.mp4, .mov, .avi, .mkv)</p>
        </div>
        <button type="submit" id="submitBtn">🚀 Process Video</button>
    </form>
    
    <div id="status"></div>
    <div id="taskInfo" class="task-info hidden">
        <h3>Task Information</h3>
        <p><strong>Task ID:</strong> <span id="taskId"></span></p>
        <p><strong>Status:</strong> <span id="taskStatus"></span></p>
        <div class="progress-bar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        <p id="progressText">Processing...</p>
    </div>
    
    <script>
        let currentTaskId = null;
        let statusCheckInterval = null;
        
        document.getElementById('uploadForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const statusDiv = document.getElementById('status');
            const taskInfoDiv = document.getElementById('taskInfo');
            const submitBtn = document.getElementById('submitBtn');
            
            // Disable form and show initial status
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ Uploading...';
            statusDiv.innerHTML = '<div class="info">⏳ Uploading video file...</div>';
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    currentTaskId = result.task_id;
                    statusDiv.innerHTML = '<div class="info">✅ Video uploaded successfully! Processing started.</div>';
                    
                    // Show task info
                    document.getElementById('taskId').textContent = currentTaskId;
                    document.getElementById('taskStatus').textContent = 'PROCESSING';
                    taskInfoDiv.classList.remove('hidden');
                    
                    // Start status checking
                    startStatusCheck();
                } else {
                    statusDiv.innerHTML = `<div class="error">❌ Upload failed: ${result.error || 'Unknown error'}</div>`;
                    submitBtn.disabled = false;
                    submitBtn.textContent = '🚀 Process Video';
                }
            } catch (error) {
                statusDiv.innerHTML = `<div class="error">❌ Upload error: ${error.message}</div>`;
                submitBtn.disabled = false;
                submitBtn.textContent = '🚀 Process Video';
            }
        });
        
        function startStatusCheck() {
            if (statusCheckInterval) {
                clearInterval(statusCheckInterval);
            }
            
            statusCheckInterval = setInterval(async () => {
                if (!currentTaskId) return;
                
                try {
                    const response = await fetch(`/task/${currentTaskId}`);
                    const result = await response.json();
                    
                    if (response.ok) {
                        updateTaskStatus(result);
                        
                        if (result.state === 'SUCCESS' || result.state === 'FAILURE') {
                            clearInterval(statusCheckInterval);
                            handleTaskCompletion(result);
                        }
                    }
                } catch (error) {
                    console.error('Error checking task status:', error);
                }
            }, 2000); // Check every 2 seconds
        }
        
        function updateTaskStatus(result) {
            const statusSpan = document.getElementById('taskStatus');
            const progressText = document.getElementById('progressText');
            const progressFill = document.getElementById('progressFill');
            
            statusSpan.textContent = result.state;
            
            // Format ETA display
            let etaDisplay = '';
            if (result.eta_minutes !== null && result.eta_minutes !== undefined) {
                if (result.eta_minutes === 0) {
                    etaDisplay = ' - Completed!';
                } else if (result.eta_minutes === 1) {
                    etaDisplay = ' - ETA: ~1 minute';
                } else {
                    etaDisplay = ` - ETA: ~${Math.round(result.eta_minutes)} minutes`;
                }
            }
            
            if (result.state === 'PENDING') {
                progressText.innerHTML = `<span class="spinner"></span>Task is waiting to be processed...${etaDisplay}`;
                progressFill.style.width = '10%';
            } else if (result.state === 'PROGRESS') {
                progressText.innerHTML = `<span class="spinner"></span>${result.status || 'Processing...'}${etaDisplay}`;
                progressFill.style.width = '50%';
            } else if (result.state === 'SUCCESS') {
                progressText.textContent = '✅ Task completed successfully!';
                progressFill.style.width = '100%';
                progressFill.style.backgroundColor = '#28a745';
            } else if (result.state === 'FAILURE') {
                progressText.textContent = '❌ Task failed';
                progressFill.style.width = '100%';
                progressFill.style.backgroundColor = '#dc3545';
            }
        }
        
        function handleTaskCompletion(result) {
            const statusDiv = document.getElementById('status');
            const submitBtn = document.getElementById('submitBtn');
            
            if (result.state === 'SUCCESS') {
                if (result.result && result.result.output_filename) {
                    statusDiv.innerHTML = '<div class="success">✅ Video processed successfully! Redirecting to result page...</div>';
                    setTimeout(() => {
                        window.location.href = `/result?file=${result.result.output_filename}`;
                    }, 2000);
                } else {
                    statusDiv.innerHTML = '<div class="success">✅ Video processed successfully!</div>';
                }
            } else {
                statusDiv.innerHTML = `<div class="error">❌ Processing failed: ${result.error || 'Unknown error'}</div>`;
            }
            
            // Re-enable form
            submitBtn.disabled = false;
            submitBtn.textContent = '🚀 Process Video';
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main page with file upload form"""
    return render_template_string(UPLOAD_TEMPLATE)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and trigger pipeline processing with Celery"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get paths from config
        input_folder, output_folder = get_config_paths()
        
        # Clean up old output files to avoid confusion
        output_dir = Path(output_folder)
        output_dir.mkdir(parents=True, exist_ok=True)
        for old_file in output_dir.glob('*.mp4'):
            try:
                old_file.unlink()
                logger.info(f"🗑️ Removed old output file: {old_file.name}")
            except Exception as e:
                logger.warning(f"⚠️ Could not remove old file {old_file.name}: {str(e)}")
        
        # Create input directory
        input_dir = Path(input_folder)
        input_dir.mkdir(exist_ok=True)
        
        # Clean up old input files
        for old_file in input_dir.glob('*'):
            try:
                old_file.unlink()
                logger.info(f"🗑️ Removed old input file: {old_file.name}")
            except Exception as e:
                logger.warning(f"⚠️ Could not remove old file {old_file.name}: {str(e)}")
        
        # Save uploaded file
        file_path = input_dir / file.filename
        file.save(file_path)
        
        logger.info(f"File uploaded: {file_path}")
        
        # Small delay to ensure file is fully written
        import time
        time.sleep(1)
        
        # Start Celery task for video processing
        task = process_video_task.delay(file.filename)
        
        # Return task ID for status tracking
        return jsonify({
            'message': 'Video upload successful! Processing started.',
            'task_id': task.id,
            'status': 'PROCESSING',
            'filename': file.filename
        })
            
    except Exception as e:
        # Add traceback to logs for detailed error information
        logger.error("❌ Upload error occurred:")
        logger.error(f"Error: {str(e)}")
        logger.error("Full traceback:")
        traceback.print_exc()
        
        return jsonify({
            'error': 'Upload failed',
            'details': str(e)
        }), 500

@app.route('/task/<task_id>')
def get_task_status(task_id):
    """Get the status of a Celery task"""
    try:
        task = process_video_task.AsyncResult(task_id)
        
        # Calculate ETA for processing tasks
        eta_minutes = None
        if task.state in ['PENDING', 'PROGRESS']:
            # Estimate processing time based on typical video processing
            # Average processing time: 2-4 minutes for 1-minute videos
            estimated_processing_time = 3  # minutes
            
            if task.state == 'PENDING':
                eta_minutes = estimated_processing_time
            elif task.state == 'PROGRESS':
                # Calculate remaining time based on progress
                progress = task.info.get('progress', 0) if task.info else 0
                if progress > 0:
                    # Estimate remaining time based on progress percentage
                    remaining_progress = 100 - progress
                    eta_minutes = max(1, (remaining_progress / progress) * estimated_processing_time)
                else:
                    eta_minutes = estimated_processing_time
        
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Task is waiting to be processed...',
                'eta_minutes': eta_minutes
            }
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'status': task.info.get('status', 'Processing...'),
                'progress': task.info.get('progress', 0),
                'eta_minutes': eta_minutes
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'status': 'Task completed successfully!',
                'result': task.result,
                'eta_minutes': 0
            }
        elif task.state == 'FAILURE':
            response = {
                'state': task.state,
                'status': 'Task failed',
                'error': str(task.info),
                'eta_minutes': None
            }
        else:
            response = {
                'state': task.state,
                'status': 'Unknown state',
                'eta_minutes': None
            }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting task status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/task/<task_id>/result')
def get_task_result(task_id):
    """Get the result of a completed Celery task"""
    try:
        task = process_video_task.AsyncResult(task_id)
        
        if task.state == 'SUCCESS':
            result = task.result
            if result.get('status') == 'SUCCESS' and result.get('short_clips'):
                # Redirect to result page with short clips data
                return redirect(url_for('show_result', 
                                      file=result['output_filename'],
                                      video_base_name=result.get('video_base_name'),
                                      short_clips=len(result.get('short_clips', []))))
            elif result.get('status') == 'SUCCESS' and result.get('output_filename'):
                # Fallback for videos without short clips
                return redirect(url_for('show_result', file=result['output_filename']))
            else:
                return jsonify(result)
        elif task.state == 'FAILURE':
            return jsonify({
                'error': 'Task failed',
                'details': str(task.info)
            }), 500
        else:
            return jsonify({
                'error': 'Task not completed yet',
                'state': task.state
            }), 202
            
    except Exception as e:
        logger.error(f"Error getting task result: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/task/<task_id>/cleanup', methods=['POST'])
def cleanup_task_files(task_id):
    """Clean up files after task completion"""
    try:
        task = process_video_task.AsyncResult(task_id)
        
        if task.state == 'SUCCESS' and task.result:
            filename = task.result.get('filename')
            if filename:
                cleanup_task.delay(filename)
                return jsonify({'message': 'Cleanup task started'})
        
        return jsonify({'error': 'No cleanup needed or task not completed'}), 400
        
    except Exception as e:
        logger.error(f"Error starting cleanup task: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/cleanup/<video_base_name>', methods=['POST'])
def manual_cleanup(video_base_name):
    """Manually trigger cleanup for a specific video"""
    try:
        # Start the auto-cleanup task immediately
        task = auto_cleanup_task.delay(video_base_name)
        
        return jsonify({
            'message': f'Manual cleanup started for {video_base_name}',
            'task_id': task.id
        })
        
    except Exception as e:
        logger.error(f"Error starting manual cleanup: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Video automation pipeline is running'})

@app.route('/debug')
def debug_info():
    """Debug endpoint to show environment and system info"""
    try:
        # Check ffmpeg
        ffmpeg_status = "unknown"
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            ffmpeg_status = "available" if result.returncode == 0 else "error"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            ffmpeg_status = "not_found"
        
        # Check directories
        input_folder, output_folder = get_config_paths()
        input_dir = Path(input_folder)
        output_dir = Path(output_folder)
        
        return jsonify({
            'ffmpeg_status': ffmpeg_status,
            'input_directory_exists': input_dir.exists(),
            'output_directory_exists': output_dir.exists(),
            'input_directory_writable': input_dir.is_dir() and os.access(input_dir, os.W_OK),
            'output_directory_writable': output_dir.is_dir() and os.access(output_dir, os.W_OK),
            'python_version': sys.version,
            'working_directory': os.getcwd(),
            'environment_variables': {
                'PORT': os.environ.get('PORT'),
                'PYTHONPATH': os.environ.get('PYTHONPATH')
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logs')
def get_logs():
    """Get recent logs"""
    try:
        log_file = Path('pipeline.log')
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = f.read()
            return jsonify({'logs': logs})
        else:
            return jsonify({'logs': 'No logs available yet'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/result')
def show_result():
    """Display processed video with download and logs"""
    try:
        filename = request.args.get('file')
        video_base_name = request.args.get('video_base_name')
        
        if not filename:
            return jsonify({'error': 'No file specified'}), 400
        
        _, output_folder = get_config_paths()
        
        # If we have video_base_name, look for short clips
        short_clips = []
        if video_base_name:
            output_dir = Path(output_folder)
            pattern = f"{video_base_name}_short_*.mp4"
            for clip_file in output_dir.glob(pattern):
                if clip_file.is_file():
                    clip_size = round(clip_file.stat().st_size / (1024 * 1024), 2)
                    short_clips.append({
                        'filename': clip_file.name,
                        'url': f'/output/{clip_file.name}',
                        'size': f"{clip_size} MB"
                    })
            # Sort clips by name (short_1, short_2, etc.)
            short_clips.sort(key=lambda x: x['filename'])
        
        # Main video info
        video_path = Path(output_folder) / filename
        main_video = None
        if video_path.exists():
            file_size = video_path.stat().st_size
            file_size_mb = round(file_size / (1024 * 1024), 2)
            main_video = {
                'filename': filename,
                'url': f'/output/{filename}',
                'size': f"{file_size_mb} MB"
            }
        
        # Read logs from pipeline.log
        log_file = Path('pipeline.log')
        logs = "No logs available yet."
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = f.read()
            except Exception as e:
                logs = f"Error reading logs: {str(e)}"
        
        # Get current timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return render_template('result.html', 
                             main_video=main_video,
                             short_clips=short_clips,
                             video_base_name=video_base_name,
                             timestamp=timestamp,
                             logs=logs)
    except Exception as e:
        logger.error(f"Error in show_result: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/output/<path:filename>')
def serve_video(filename):
    """Serve output video files"""
    try:
        _, output_folder = get_config_paths()
        return send_from_directory(output_folder, filename)
    except Exception as e:
        logger.error(f"Error serving video {filename}: {str(e)}")
        return jsonify({'error': f'File not found: {filename}'}), 404

if __name__ == '__main__':
    # Validate environment before starting
    validate_environment()
    
    # Get port from environment (Railway sets this)
    port = int(os.environ.get('PORT', 8000))
    
    logger.info(f"🚀 Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
