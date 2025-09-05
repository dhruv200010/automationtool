import os
import sys
import json
import subprocess
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string, render_template, send_from_directory, redirect, url_for
import logging

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
        log_file = Path('/app/pipeline.log')
        if log_file.exists():
            log_file.unlink()
            logger.info("🗑️ Cleared previous pipeline logs")
    except Exception as e:
        logger.warning(f"⚠️ Could not clear logs: {str(e)}")

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
    
    # Check for required directories
    required_dirs = ['/app/input', '/app/output']
    for dir_path in required_dirs:
        Path(dir_path).mkdir(exist_ok=True)
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

# HTML template for file upload
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
        .status { margin: 20px 0; padding: 10px; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
    </style>
</head>
<body>
    <h1>🎬 Video Automation Pipeline</h1>
    <p>Upload a video file to process it through the automation pipeline.</p>
    
    <form action="/upload" method="post" enctype="multipart/form-data">
        <div class="upload-area">
            <input type="file" name="file" accept=".mp4,.mov,.avi,.mkv" required>
            <p>Select a video file (.mp4, .mov, .avi, .mkv)</p>
        </div>
        <button type="submit">🚀 Process Video</button>
    </form>
    
    <div id="status"></div>
    
    <script>
        document.querySelector('form').addEventListener('submit', function(e) {
            const statusDiv = document.getElementById('status');
            statusDiv.innerHTML = '<div class="info">⏳ Processing video... This may take a few minutes. You will be redirected to the result page when complete.</div>';
        });
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
    """Handle file upload and trigger pipeline processing"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Clear previous logs and old output files
        clear_pipeline_logs()
        
        # Clean up old output files to avoid confusion
        output_dir = Path('/app/output')
        output_dir.mkdir(exist_ok=True)
        for old_file in output_dir.glob('*.mp4'):
            try:
                old_file.unlink()
                logger.info(f"🗑️ Removed old output file: {old_file.name}")
            except Exception as e:
                logger.warning(f"⚠️ Could not remove old file {old_file.name}: {str(e)}")
        
        # Create input directory
        input_dir = Path('/app/input')
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
        
        # Trigger pipeline processing in background
        try:
            # Run the pipeline
            result = subprocess.run(
                ['python', 'run_pipeline.py'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Extract the output filename from the logs
                output_filename = None
                for line in result.stdout.split('\n'):
                    if 'Output video saved to:' in line:
                        output_filename = Path(line.split('Output video saved to: ')[1]).name
                        break
                
                if output_filename:
                    # Redirect to result page
                    return redirect(url_for('show_result', file=output_filename))
                else:
                    return jsonify({
                        'message': 'Video processed successfully!',
                        'output': result.stdout,
                        'file': str(file_path)
                    })
            else:
                # ✅ Add detailed error logging
                logger.error("❌ Pipeline processing failed:")
                logger.error(f"Return code: {result.returncode}")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                
                return jsonify({
                    'error': 'Pipeline processing failed',
                    'details': result.stderr,
                    'return_code': result.returncode,
                    'stdout': result.stdout
                }), 500
                
        except subprocess.TimeoutExpired as e:
            logger.error(f"❌ Processing timeout: {str(e)}")
            return jsonify({
                'error': 'Processing timeout - video may be too large for free plan',
                'message': 'Try with a smaller video file'
            }), 408
            
    except Exception as e:
        # ✅ Add traceback to logs for detailed error information
        logger.error("❌ Upload error occurred:")
        logger.error(f"Error: {str(e)}")
        logger.error("Full traceback:")
        traceback.print_exc()
        
        return jsonify({
            'error': 'Upload failed',
            'details': str(e)
        }), 500

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
        input_dir = Path('/app/input')
        output_dir = Path('/app/output')
        
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
        log_file = Path('/app/pipeline.log')
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
        if not filename:
            return jsonify({'error': 'No file specified'}), 400
        
        video_path = Path('/app/output') / filename
        if not video_path.exists():
            return jsonify({'error': f'Video file not found: {filename}'}), 404
        
        # Read logs from pipeline.log
        log_file = Path('/app/pipeline.log')
        logs = "No logs available yet."
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = f.read()
            except Exception as e:
                logs = f"Error reading logs: {str(e)}"
        
        # Get file info
        file_size = video_path.stat().st_size if video_path.exists() else 0
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        # Get current timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return render_template('result.html', 
                             video_url=f'/output/{filename}',
                             filename=filename,
                             file_size=f"{file_size_mb} MB",
                             timestamp=timestamp,
                             logs=logs)
    except Exception as e:
        logger.error(f"Error in show_result: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/output/<path:filename>')
def serve_video(filename):
    """Serve output video files"""
    try:
        return send_from_directory('/app/output', filename)
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
