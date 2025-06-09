import subprocess
import sys
import os
import logging
from datetime import datetime

# Set up logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pipeline.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def run_command(command, step_name):
    """Run a command and log its output"""
    logger.info(f"Starting: {step_name}")
    try:
        # Run the command and capture output in real-time
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            shell=True
        )
        
        # Stream the output in real-time
        for line in process.stdout:
            # Remove any ANSI color codes and extra whitespace
            clean_line = line.strip()
            if clean_line:
                logger.info(clean_line)
        
        # Wait for the process to complete
        return_code = process.wait()
        
        if return_code == 0:
            logger.info(f"Completed: {step_name}")
            return True
        else:
            logger.error(f"Failed: {step_name} with return code {return_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error in {step_name}: {str(e)}")
        return False

def main():
    if len(sys.argv) != 2:
        logger.error("Usage: python run_pipeline.py <video_file_path>")
        sys.exit(1)

    video_file = sys.argv[1]
    
    # Check if video file exists
    if not os.path.exists(video_file):
        logger.error(f"Error: Video file '{video_file}' not found!")
        sys.exit(1)

    # Define the steps
    steps = [
        {
            "name": "Step 1: Process video and add subtitles",
            "command": f'python src/add_subtitles.py "{video_file}"'
        },
        {
            "name": "Step 2: Create shorts from full video",
            "command": 'python src/create_shorts.py'
        },
        {
            "name": "Step 3: Generate titles/tags/descriptions",
            "command": 'python src/generate_titles.py'
        },
        {
            "name": "Step 4: Upload shorts and schedule",
            "command": 'python src/upload_shorts.py'
        }
    ]

    # Run each step
    for step in steps:
        if not run_command(step["command"], step["name"]):
            logger.error(f"Pipeline failed at {step['name']}")
            sys.exit(1)

    logger.info("All steps in pipeline completed successfully!")

if __name__ == "__main__":
    main()
