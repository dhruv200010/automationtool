import os
import sys
import json
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
import logging

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            statusDiv.innerHTML = '<div class="info">⏳ Processing video... This may take a few minutes.</div>';
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
        
        # Create input directory
        input_dir = Path('/app/input')
        input_dir.mkdir(exist_ok=True)
        
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
                return jsonify({
                    'message': 'Video processed successfully!',
                    'output': result.stdout,
                    'file': str(file_path)
                })
            else:
                return jsonify({
                    'error': 'Pipeline processing failed',
                    'details': result.stderr
                }), 500
                
        except subprocess.TimeoutExpired:
            return jsonify({
                'error': 'Processing timeout - video may be too large for free plan',
                'message': 'Try with a smaller video file'
            }), 408
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Video automation pipeline is running'})

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

if __name__ == '__main__':
    # Create necessary directories
    Path('/app/input').mkdir(exist_ok=True)
    Path('/app/output').mkdir(exist_ok=True)
    
    # Get port from environment (Railway sets this)
    port = int(os.environ.get('PORT', 8000))
    
    logger.info(f"Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
