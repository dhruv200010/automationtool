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

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()

def normalize_paths_in_config():
    """Normalize paths in master_config.json to use double backslashes"""
    config_path = PROJECT_ROOT / "config" / "master_config.json"
    if not config_path.exists():
        logger.error("Error: master_config.json not found in config directory!")
        sys.exit(1)
    
    try:
        # First read the file content as a raw string
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Replace single backslashes with double backslashes before JSON parsing
            content = content.replace('\\', '\\\\')
            config = json.loads(content)
        
        # Convert paths to use double backslashes
        if 'input_folder' in config:
            config['input_folder'] = str(Path(config['input_folder']).resolve()).replace('\\', '\\\\')
        if 'output_folder' in config:
            config['output_folder'] = str(Path(config['output_folder']).resolve()).replace('\\', '\\\\')
        
        # Write back the normalized config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info("Normalized paths in master_config.json")
    except Exception as e:
        logger.error(f"Error normalizing paths in master_config.json: {str(e)}")
        sys.exit(1)

def get_all_videos(folder_path: Path) -> list[Path]:
    """Get all video files from the specified folder"""
    if not folder_path.exists():
        logger.error(f"Error: Input folder '{folder_path}' not found!")
        sys.exit(1)
    
    # Supported video formats
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv']
    
    # Get all video files in the folder
    video_files = []
    for ext in video_extensions:
        video_files.extend(folder_path.glob(f'*{ext}'))
    
    if not video_files:
        logger.error(f"Error: No video files found in '{folder_path}'!")
        sys.exit(1)
    
    # Sort by modification time
    video_files.sort(key=lambda x: x.stat().st_mtime)
    logger.info(f"Found {len(video_files)} video files")
    return video_files

def get_input_folder() -> Path:
    """Get input folder path from config file"""
    config_path = PROJECT_ROOT / "config" / "master_config.json"
    if not config_path.exists():
        logger.error("Error: master_config.json not found in config directory!")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            input_folder = config.get('input_folder')
            if not input_folder:
                logger.error("Error: 'input_folder' not found in master_config.json!")
                sys.exit(1)
            return Path(input_folder).expanduser().resolve()
    except json.JSONDecodeError:
        logger.error("Error: Invalid JSON in master_config.json!")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading master_config.json: {str(e)}")
        sys.exit(1)

def run_command(command: str, step_name: str) -> bool:
    """Run a command and log its output"""
    logger.info(f"Starting: {step_name}")
    try:
        # Set up environment with PYTHONPATH
        env = os.environ.copy()
        env['PYTHONPATH'] = str(PROJECT_ROOT)
        
        # Run the command and capture output in real-time
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            shell=True,
            env=env
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

def process_video(video_file: Path) -> bool:
    """Process a single video through the pipeline"""
    logger.info(f"\nProcessing video: {video_file}")
    
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
            logger.error(f"Pipeline failed at {step['name']} for video {video_file}")
            return False

    logger.info(f"Successfully processed video: {video_file}")
    return True

def main():
    # Normalize paths in master_config.json first
    normalize_paths_in_config()
    
    # Get input folder from config and find all videos
    input_folder = get_input_folder()
    video_files = get_all_videos(input_folder)
    
    # Track success and failure
    successful_videos = []
    failed_videos = []
    
    # Process each video
    for video_file in video_files:
        try:
            if process_video(video_file):
                successful_videos.append(video_file)
            else:
                failed_videos.append(video_file)
        except Exception as e:
            logger.error(f"Unexpected error processing video {video_file}: {str(e)}")
            failed_videos.append(video_file)
    
    # Print summary
    logger.info("\nPipeline Processing Summary:")
    logger.info(f"Total videos processed: {len(video_files)}")
    logger.info(f"Successfully processed: {len(successful_videos)}")
    logger.info(f"Failed to process: {len(failed_videos)}")
    
    if failed_videos:
        logger.info("\nFailed videos:")
        for video in failed_videos:
            logger.info(f"- {video}")
    
    if failed_videos:
        sys.exit(1)  # Exit with error if any videos failed
    else:
        logger.info("\nAll videos processed successfully!")

if __name__ == "__main__":
    main()
