import subprocess
import sys
import os
import logging
import json
from datetime import datetime
from pathlib import Path
import re

# Set up logging with UTF-8 encoding and emojis
class EmojiFormatter(logging.Formatter):
    # ANSI color codes
    COLORS = {
        'blue': '\033[94m',    # Step 1
        'green': '\033[92m',   # Step 2
        'yellow': '\033[93m',  # Step 3
        'red': '\033[91m',     # Step 4
        'cyan': '\033[96m',    # Processing new video
        'reset': '\033[0m'     # Reset color
    }

    def format(self, record):
        # Skip adding emojis for separator lines
        if "⏳" in record.msg or "♻️" in record.msg or "⭐" in record.msg:
            return super().format(record)
            
        # Add color to processing new video separator
        elif "♻️" in record.msg and "Processing new video" in record.msg:
            return f"{self.COLORS['cyan']}{super().format(record)}{self.COLORS['reset']}"
            
        # Add emojis based on log level and message content
        if record.levelno >= logging.ERROR:
            record.msg = f"❌  {record.msg}"
        elif record.levelno >= logging.WARNING:
            record.msg = f"⚠️  {record.msg}"
        elif record.levelno >= logging.INFO:
            # Add specific emojis for common operations
            msg = record.msg.lower()
            
            # Check for completed status first
            if "completed" in msg:
                shorts_match = re.search(r'created (\d+) shorts', msg)
                if shorts_match and "step 2" in msg:
                    # Let it match even if emojis are there
                    record.msg = f"{self.COLORS['green']}✂️  Completed: Step 2: Create shorts from full video (created {shorts_match.group(1)} shorts){self.COLORS['reset']}"
                else:
                    # Apply a default emoji only if not already present
                    if not record.msg.startswith("✅"):
                        record.msg = f"✅  {record.msg}"
            # Pipeline steps with colors - only for main step messages
            elif "step 1:" in msg and "process video and add subtitles" in msg:
                record.msg = f"{self.COLORS['blue']}🎬  {record.msg}{self.COLORS['reset']}"  # Video processing
            elif "step 2:" in msg and "create shorts from full video" in msg:
                record.msg = f"{self.COLORS['green']}✂️  {record.msg}{self.COLORS['reset']}"  # Creating shorts
            elif "step 3:" in msg and "generate titles/tags/descriptions" in msg:
                record.msg = f"{self.COLORS['yellow']}📝  {record.msg}{self.COLORS['reset']}"  # Generating titles
            elif "step 4:" in msg and "upload shorts and schedule" in msg:
                record.msg = f"{self.COLORS['red']}📤  {record.msg}{self.COLORS['reset']}"  # Uploading
            # API and Content Generation
            elif "generating title" in msg:
                record.msg = f"🎯  {record.msg}"  # Targeting content
            elif "sending request" in msg:
                record.msg = f"🌐  {record.msg}"  # API request
            elif "api response" in msg:
                record.msg = f"📡  {record.msg}"  # API response
            elif "hashtags" in msg:
                record.msg = f"🏷️  {record.msg}"  # Tags
            elif "description" in msg:
                record.msg = f"📄  {record.msg}"  # Description
            elif "extracted" in msg:
                record.msg = f"🔖  {record.msg}"  # Extracted content
            # Other operations
            elif "starting" in msg:
                record.msg = f"🚀  {record.msg}"
            elif "processing" in msg:
                # Remove gear icon for processing messages
                record.msg = f"{record.msg}"
            elif "found" in msg:
                record.msg = f"🔍  {record.msg}"
            elif "saved" in msg:
                record.msg = f"💾  {record.msg}"
            elif "upload" in msg:
                record.msg = f"📤  {record.msg}"
            elif "schedule" in msg:
                record.msg = f"📅  {record.msg}"
            elif "error" in msg:
                record.msg = f"❌  {record.msg}"
            elif "warning" in msg:
                record.msg = f"⚠️  {record.msg}"
            elif "successfully" in msg:
                record.msg = f"✅  {record.msg}"  # Success messages
            elif "burning" in msg:
                record.msg = f"🔥  {record.msg}"  # Burning subtitles
            elif "temporary" in msg or "cleaned" in msg:
                record.msg = f"🗑️  {record.msg}"  # Cleanup operations
            elif "clip" in msg:
                # Extract clip number and total if present
                clip_match = re.search(r'Processing clip (\d+)/(\d+)', msg)
                if clip_match:
                    clip_num = clip_match.group(1)
                    total_clips = clip_match.group(2)
                    record.msg = f"📋  Clip {clip_num}/{total_clips}  {record.msg}"  # Clip processing
                else:
                    record.msg = f"📋  {record.msg}"  # General clip message
            # Regular step messages without colors
            elif "step" in msg:
                if "step 1" in msg:
                    record.msg = f"🎬  {record.msg}"  # Video processing
                elif "step 2" in msg:
                    record.msg = f"✂️  {record.msg}"  # Creating shorts
                elif "step 3" in msg:
                    record.msg = f"📝  {record.msg}"  # Generating titles
                elif "step 4" in msg:
                    record.msg = f"📤  {record.msg}"  # Uploading
        return super().format(record)

# Set up logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pipeline.log', encoding='utf-8')
    ]
)

# Apply the emoji formatter to the root logger
for handler in logging.getLogger().handlers:
    handler.setFormatter(EmojiFormatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger(__name__)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()

def get_pipeline_config():
    """Get pipeline configuration from master_config.json"""
    config_path = PROJECT_ROOT / "config" / "master_config.json"
    if not config_path.exists():
        logger.error("Error: master_config.json not found in config directory!")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            pipeline_steps = config.get('pipeline_steps', {})
            if not pipeline_steps:
                logger.error("Error: 'pipeline_steps' not found in master_config.json!")
                sys.exit(1)
            return config
    except json.JSONDecodeError:
        logger.error("Error: Invalid JSON in master_config.json!")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error reading master_config.json: {str(e)}")
        sys.exit(1)

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
            
        # Fix common JSON formatting issues
        content = content.replace('""', '"')  # Remove double quotes
        content = content.replace('\\', '\\\\')  # Convert single backslashes to double
        
        # Parse the JSON
        config = json.loads(content)
        
        # Ensure paths are properly formatted
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

def process_video(video_file: Path, config: dict) -> bool:
    """Process a single video through the pipeline"""
    logger.info(f"Processing video: {video_file}")
    
    # Construct the path to the subtitled video
    output_root = Path(config['output_folder']).expanduser().resolve()
    subtitled_video_path = output_root / f"{video_file.stem}_with_subs.mp4"

    # Define the steps with their corresponding config keys
    steps = [
        {
            "name": "Step 1: Process video and add subtitles",
            "command": f'python src/add_subtitles.py "{video_file}"',
            "config_key": "add_subtitles"
        },
        {
            "name": "Step 1.5: Trim silence from video",
            "command": f'python src/trim_silence.py "{subtitled_video_path}"',
            "config_key": "trim_silence"
        },
        {
            "name": "Step 2: Create shorts from full video",
            "command": 'python src/create_shorts.py',
            "config_key": "create_shorts"
        },
        {
            "name": "Step 3: Generate titles/tags/descriptions",
            "command": 'python src/generate_titles.py',
            "config_key": "generate_titles"
        },
        {
            "name": "Step 4: Upload shorts and schedule",
            "command": 'python src/upload_shorts.py',
            "config_key": "upload_shorts"
        }
    ]

    # Run each step if enabled in config
    for step in steps:
        # Check if the step is enabled in config
        if not config['pipeline_steps'].get(step['config_key'], False):
            logger.info(f"{step['name']} is disabled in config. Stopping pipeline.")
            return True  # Return True since this is an intentional stop
            
        if not run_command(step["command"], step["name"]):
            logger.error(f"Pipeline failed at {step['name']} for video {video_file}")
            return False

    logger.info(f"Successfully processed video: {video_file}")
    return True

def display_final_metadata_summary(config: dict):
    """Display final metadata summary from shorts_titles.json"""
    try:
        output_folder = Path(config['output_folder']).expanduser().resolve()
        titles_file = output_folder / "shorts_titles.json"
        
        if titles_file.exists():
            with open(titles_file, 'r', encoding='utf-8') as f:
                titles_data = json.load(f)
            
            logger.info("\n📋  Final Metadata Summary:")
            for path, info in titles_data.items():
                if info.get('uploaded'):
                    video_id = info.get('youtube_id', 'Unknown')
                    title = info.get('title', 'No title')
                    upload_date = info.get('upload_date', 'Unknown')
                    logger.info(f"🎥  Video ID: {video_id}")
                    logger.info(f"📝  Title: {title}")
                    logger.info(f"📅  Upload Date: {upload_date}")
                    logger.info("---")
    except Exception as e:
        logger.error(f"Error reading final metadata: {str(e)}")

def main():
    # Normalize paths in master_config.json first
    normalize_paths_in_config()
    
    # Get configuration
    config = get_pipeline_config()
    
    # Get input folder from config and find all videos
    input_folder = Path(config['input_folder']).expanduser().resolve()
    video_files = get_all_videos(input_folder)
    
    # Track success and failure
    successful_videos = []
    failed_videos = []
    
    # Process each video
    for video_file in video_files:
        # Add visual separator for new video
        logger.info("♻️ ♻️ ♻️  Processing new video  ♻️ ♻️ ♻️")
        logger.info(f"🎥  {video_file}")
        logger.info("⏳ ⏳ ⏳  Starting processing  ⏳ ⏳ ⏳")
        
        try:
            if process_video(video_file, config):
                successful_videos.append(video_file)
            else:
                failed_videos.append(video_file)
        except Exception as e:
            logger.error(f"Unexpected error processing video {video_file}: {str(e)}")
            failed_videos.append(video_file)
    
    # Print summary
    logger.info("⏳ ⏳ ⏳  Pipeline Summary  ⏳ ⏳ ⏳")
    logger.info(f"📊  Total videos processed: {len(video_files)}")
    logger.info(f"✅  Successfully processed: {len(successful_videos)}")
    logger.info(f"❌  Failed to process: {len(failed_videos)}")
    
    if failed_videos:
        logger.info("\nFailed videos:")
        for video in failed_videos:
            logger.info(f"- {video}")
    
    # Display final metadata summary
    display_final_metadata_summary(config)
    
    if failed_videos:
        sys.exit(1)  # Exit with error if any videos failed
    else:
        logger.info("⭐  All videos processed successfully!")

if __name__ == "__main__":
    main()
