#!/usr/bin/env python3
"""
Startup script for video automation pipeline with Celery and Redis
Supports both local development and production deployment
"""

import os
import sys
import subprocess
import time
import signal
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServiceManager:
    def __init__(self):
        self.processes = []
        self.running = True
        
    def add_process(self, process):
        """Add a process to the manager"""
        self.processes.append(process)
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"🛑 Received signal {signum}, shutting down services...")
        self.running = False
        self.shutdown()
        
    def shutdown(self):
        """Shutdown all managed processes"""
        for process in self.processes:
            if process.poll() is None:  # Process is still running
                logger.info(f"🛑 Terminating process {process.pid}")
                process.terminate()
                
        # Wait for processes to terminate
        for process in self.processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning(f"⚠️ Force killing process {process.pid}")
                process.kill()
                
    def start_redis(self):
        """Start Redis server"""
        logger.info("🚀 Starting Redis server...")
        
        # Check if Redis is already running
        try:
            result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and 'PONG' in result.stdout:
                logger.info("✅ Redis server is already running")
                return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Start Redis server
        try:
            if os.name == 'nt':  # Windows
                # For Windows, we'll use a different approach
                logger.info("💻 Windows detected - Redis should be installed separately")
                return None
            else:  # Unix-like systems
                process = subprocess.Popen(['redis-server', '--daemonize', 'yes'])
                time.sleep(2)  # Give Redis time to start
                logger.info("✅ Redis server started")
                return process
        except FileNotFoundError:
            logger.warning("⚠️ Redis server not found - make sure Redis is installed")
            return None
            
    def start_celery_worker(self):
        """Start Celery worker"""
        logger.info("🚀 Starting Celery worker...")
        
        # Set environment variables
        env = os.environ.copy()
        env['PYTHONPATH'] = str(project_root)
        
        # Celery worker command
        cmd = [
            sys.executable, '-m', 'celery',
            '-A', 'celery_app',
            'worker',
            '--loglevel=info',
            '--concurrency=1',
            '--pool=solo',
            '--without-gossip',
            '--without-mingle',
            '--without-heartbeat'
        ]
        
        # Add additional options for Hostinger KVM 2 deployment
        cmd.extend([
            '--max-tasks-per-child=1',
            '--time-limit=1800',
            '--soft-time-limit=1500'
        ])
        logger.info("🖥️ Hostinger KVM 2 deployment - using optimized settings")
        
        try:
            process = subprocess.Popen(cmd, env=env)
            logger.info(f"✅ Celery worker started with PID {process.pid}")
            return process
        except Exception as e:
            logger.error(f"❌ Failed to start Celery worker: {str(e)}")
            return None
            
    def start_flask_app(self):
        """Start Flask application"""
        logger.info("🚀 Starting Flask application...")
        
        # Set environment variables
        env = os.environ.copy()
        env['PYTHONPATH'] = str(project_root)
        
        try:
            process = subprocess.Popen([sys.executable, 'app.py'], env=env)
            logger.info(f"✅ Flask app started with PID {process.pid}")
            return process
        except Exception as e:
            logger.error(f"❌ Failed to start Flask app: {str(e)}")
            return None
            
    def run(self):
        """Run all services"""
        logger.info("🎬 Video Automation Pipeline - Service Manager")
        logger.info("=" * 50)
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Start Redis
        redis_process = self.start_redis()
        if redis_process:
            self.add_process(redis_process)
            
        # Start Celery worker
        celery_process = self.start_celery_worker()
        if celery_process:
            self.add_process(celery_process)
        else:
            logger.error("❌ Failed to start Celery worker - exiting")
            return
            
        # Start Flask app
        flask_process = self.start_flask_app()
        if flask_process:
            self.add_process(flask_process)
        else:
            logger.error("❌ Failed to start Flask app - exiting")
            return
            
        logger.info("✅ All services started successfully!")
        logger.info("🌐 Web interface available at: http://localhost:8000")
        logger.info("📡 Celery worker is processing tasks in the background")
        logger.info("🛑 Press Ctrl+C to stop all services")
        
        # Monitor processes
        try:
            while self.running:
                # Check if any process has died
                for i, process in enumerate(self.processes):
                    if process.poll() is not None:
                        logger.error(f"❌ Process {process.pid} has died")
                        self.running = False
                        break
                        
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal")
            
        finally:
            self.shutdown()
            logger.info("✅ All services stopped")

def main():
    """Main function"""
    manager = ServiceManager()
    manager.run()

if __name__ == '__main__':
    main()
