#!/usr/bin/env python3
"""
Development startup script for local testing
Starts only the Flask app (assumes Redis and Celery worker are running separately)
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Start Flask app for development"""
    logger.info("🎬 Video Automation Pipeline - Development Mode")
    logger.info("=" * 50)
    logger.info("💻 Starting Flask app only (Redis and Celery should be running separately)")
    logger.info("🌐 Web interface will be available at: http://localhost:8000")
    logger.info("🛑 Press Ctrl+C to stop")
    
    # Set environment variables
    os.environ['PYTHONPATH'] = str(project_root)
    
    # Import and run the Flask app
    try:
        from app import app
        app.run(host='0.0.0.0', port=8000, debug=True)
    except Exception as e:
        logger.error(f"❌ Failed to start Flask app: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
