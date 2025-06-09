import subprocess
import sys
import os
import logging
import json
from datetime import datetime
from pathlib import Path

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

def get_latest_video(folder_path):
    """Get the most recent video file from the specified folder"""
    folder = Path(folder_path)
    if not folder.exists():
        logger.error(f"Error: Input folder '{folder_path}' not found!")
        sys.exit(1)
    
    # Supported video formats
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv']
    
    # Get all video files in the folder
    video_files = []
    for ext in video_extensions:
        video_files.extend(folder.glob(f'*{ext}'))
    
    if not video_files:
        logger.error(f"Error: No video files found in '{folder_path}'!")
        sys.exit(1)
    
    # Sort by modification time and get the most recent
    latest_video = max(video_files, key=os.path.getmtime)
    logger.info(f"Found video file: {latest_video}")
    return str(latest_video)

def get_input_folder():
    """Get input folder path from config file"""
    config_path = Path("config/master_config.json")
    if not config_path.exists():
        logger.error("Error: master_config.json not found in config directory!")
        sys.exit(1)
    
    try:
        # Read the file content as a raw string first
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Convert Windows paths to forward slashes before JSON parsing
            content = content.replace('\\', '/')
            config = json.loads(content)
            input_folder = config.get('input_folder')
            if not input_folder:
                logger.error("Error: 'input_folder' not found in master_config.json!")
                sys.exit(1)
            return input_folder
    except json.JSONDecodeError:
        logger.error("Error: Invalid JSON in master_config.json!")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading master_config.json: {str(e)}")
        sys.exit(1)

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
    # Get input folder from config and find the latest video
    input_folder = get_input_folder()
    video_file = get_latest_video(input_folder)
    
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
