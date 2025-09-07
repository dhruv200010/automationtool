import os
import sys
import json
import subprocess
import traceback
from pathlib import Path
from celery import Celery
import logging

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery('video_automation')

# Configure Celery
celery_app.conf.update(
    broker_url=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=True,
)

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

def clear_pipeline_logs():
    """Clear pipeline logs before processing a new video"""
    try:
        log_file = Path('pipeline.log')
        if log_file.exists():
            log_file.unlink()
            logger.info("🗑️ Cleared previous pipeline logs")
    except Exception as e:
        logger.warning(f"⚠️ Could not clear logs: {str(e)}")

@celery_app.task(bind=True)
def process_video_task(self, filename):
    """
    Celery task to process video through the automation pipeline
    """
    try:
        # Update task state
        self.update_state(state='PROGRESS', meta={'status': 'Starting video processing...'})
        
        # Clear previous logs and old output files
        clear_pipeline_logs()
        
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
        
        # Check if file exists first
        file_path = input_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Input file not found: {file_path}")
        
        logger.info(f"File found: {file_path}")
        
        # Clean up old input files (but keep the current one)
        for old_file in input_dir.glob('*'):
            if old_file.name != filename:  # Don't delete the current file
                try:
                    old_file.unlink()
                    logger.info(f"🗑️ Removed old input file: {old_file.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not remove old file {old_file.name}: {str(e)}")
        
        # Update task state
        self.update_state(state='PROGRESS', meta={'status': 'Running video pipeline...'})
        
        # Run the pipeline
        result = subprocess.run(
            ['python', 'run_pipeline.py'],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        if result.returncode == 0:
            # Extract the output filename from the logs
            output_filename = None
            for line in result.stdout.split('\n'):
                if 'Output video saved to:' in line:
                    output_filename = Path(line.split('Output video saved to: ')[1]).name
                    break
            
            # Clean up input file after successful processing
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"🗑️ Cleaned up input file after successful processing: {filename}")
            except Exception as e:
                logger.warning(f"⚠️ Could not clean up input file {filename}: {str(e)}")
            
            if output_filename:
                return {
                    'status': 'SUCCESS',
                    'message': 'Video processed successfully!',
                    'output_filename': output_filename,
                    'stdout': result.stdout,
                    'file': str(file_path)
                }
            else:
                return {
                    'status': 'SUCCESS',
                    'message': 'Video processed successfully!',
                    'output': result.stdout,
                    'file': str(file_path)
                }
        else:
            # Log detailed error information
            logger.error("❌ Pipeline processing failed:")
            logger.error(f"Return code: {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            
            return {
                'status': 'FAILURE',
                'error': 'Pipeline processing failed',
                'details': result.stderr,
                'return_code': result.returncode,
                'stdout': result.stdout
            }
            
    except subprocess.TimeoutExpired as e:
        logger.error(f"❌ Processing timeout: {str(e)}")
        return {
            'status': 'FAILURE',
            'error': 'Processing timeout - video may be too large',
            'message': 'Try with a smaller video file'
        }
        
    except Exception as e:
        # Add traceback to logs for detailed error information
        logger.error("❌ Task error occurred:")
        logger.error(f"Error: {str(e)}")
        logger.error("Full traceback:")
        traceback.print_exc()
        
        return {
            'status': 'FAILURE',
            'error': 'Task failed',
            'details': str(e)
        }

@celery_app.task(bind=True)
def cleanup_task(self, filename=None):
    """
    Celery task to clean up temporary files
    """
    try:
        self.update_state(state='PROGRESS', meta={'status': 'Cleaning up temporary files...'})
        
        # Get paths from config
        input_folder, output_folder = get_config_paths()
        
        # Clean up specific input file if provided
        if filename:
            input_dir = Path(input_folder)
            input_file = input_dir / filename
            if input_file.exists():
                input_file.unlink()
                logger.info(f"🗑️ Cleaned up input file: {filename}")
            else:
                logger.info(f"ℹ️ Input file not found (already cleaned): {filename}")
        
        # Clean up any temporary files in input directory
        input_dir = Path(input_folder)
        for temp_file in input_dir.glob('*'):
            if temp_file.is_file():
                try:
                    temp_file.unlink()
                    logger.info(f"🗑️ Cleaned up input file: {temp_file.name}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not remove input file {temp_file.name}: {str(e)}")
        
        # Clean up any temporary files in output directory
        output_dir = Path(output_folder)
        for temp_file in output_dir.glob('temp_*'):
            try:
                temp_file.unlink()
                logger.info(f"🗑️ Cleaned up temporary file: {temp_file.name}")
            except Exception as e:
                logger.warning(f"⚠️ Could not remove temp file {temp_file.name}: {str(e)}")
        
        return {
            'status': 'SUCCESS',
            'message': 'Cleanup completed successfully'
        }
        
    except Exception as e:
        logger.error(f"❌ Cleanup error: {str(e)}")
        return {
            'status': 'FAILURE',
            'error': 'Cleanup failed',
            'details': str(e)
        }

if __name__ == '__main__':
    celery_app.start()
