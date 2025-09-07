#!/usr/bin/env python3
"""
Celery worker startup script for video automation pipeline
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_environment():
    """Validate that required environment variables and dependencies are available"""
    logger.info("🔍 Validating environment for Celery worker...")
    
    # Check for Redis connection
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    logger.info(f"📡 Redis URL: {redis_url}")
    
    # Check for required environment variables
    required_env_vars = ['PORT']
    missing_vars = []
    
    for var in required_env_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"⚠️ Missing environment variables: {missing_vars}")
    
    # Get paths from config
    try:
        import json
        config_path = Path(__file__).parent / "config" / "master_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        input_folder = config.get('input_folder', './input')
        output_folder = config.get('output_folder', './output')
        
        # Use Hostinger KVM 2 paths
        input_folder = '/opt/video-automation/input'
        output_folder = '/opt/video-automation/output'
        logger.info("🖥️ Running on Hostinger KVM 2 - using Hostinger paths")
        
        # Create directories
        Path(input_folder).mkdir(parents=True, exist_ok=True)
        Path(output_folder).mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Input directory ready: {input_folder}")
        logger.info(f"✅ Output directory ready: {output_folder}")
        
    except Exception as e:
        logger.warning(f"⚠️ Could not read config, using default paths: {str(e)}")
        # Use Hostinger KVM 2 default paths
        Path('/opt/video-automation/input').mkdir(parents=True, exist_ok=True)
        Path('/opt/video-automation/output').mkdir(parents=True, exist_ok=True)
        logger.info("✅ Created Hostinger KVM 2 directories")
    
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
    
    try:
        import celery
        logger.info("✅ Celery library available")
    except ImportError:
        logger.error("❌ Celery library not found")
        sys.exit(1)
    
    try:
        import redis
        logger.info("✅ Redis library available")
    except ImportError:
        logger.error("❌ Redis library not found")
        sys.exit(1)
    
    logger.info("🔍 Environment validation complete")

def start_celery_worker():
    """Start the Celery worker"""
    logger.info("🚀 Starting Celery worker...")
    
    # Set environment variables for Celery
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root)
    
    # Celery worker command
    cmd = [
        'celery',
        '-A', 'celery_app',
        'worker',
        '--loglevel=info',
        '--concurrency=1',  # Single worker to avoid conflicts
        '--pool=solo',      # Use solo pool for better compatibility
        '--without-gossip',
        '--without-mingle',
        '--without-heartbeat'
    ]
    
    # Add additional options for Hostinger KVM 2 deployment
    cmd.extend([
        '--max-tasks-per-child=1',  # Restart worker after each task
        '--time-limit=1800',        # 30 minute time limit
        '--soft-time-limit=1500'    # 25 minute soft limit
    ])
    logger.info("🖥️ Hostinger KVM 2 deployment - using optimized settings")
    
    logger.info(f"📡 Starting worker with command: {' '.join(cmd)}")
    
    try:
        # Start the worker process
        process = subprocess.Popen(cmd, env=env)
        
        # Wait for the process
        process.wait()
        
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal, shutting down worker...")
        if 'process' in locals():
            process.terminate()
            process.wait()
    except Exception as e:
        logger.error(f"❌ Error starting Celery worker: {str(e)}")
        sys.exit(1)

def main():
    """Main function"""
    logger.info("🎬 Video Automation Pipeline - Celery Worker")
    logger.info("=" * 50)
    
    # Validate environment
    validate_environment()
    
    # Start the worker
    start_celery_worker()

if __name__ == '__main__':
    main()
