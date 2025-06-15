import os
import sys
import json
from pathlib import Path
import logging

# Add the project root to Python path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add src directory to Python path
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add modules directory to Python path
modules_path = project_root / "modules"
if str(modules_path) not in sys.path:
    sys.path.insert(0, str(modules_path))

from modules.silence_trimmer import SilenceTrimmer

logger = logging.getLogger(__name__)

def main():
    # Load and normalize output folder from config
    config_path = project_root / "config" / "master_config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        output_root = Path(config['output_folder']).expanduser().resolve()
    
    # Get the most recent video file from the output directory
    video_files = list(output_root.glob("*_with_subs.mp4"))
    if not video_files:
        raise FileNotFoundError("No processed video found in output directory")
    
    # Use the most recent video file
    video_path = video_files[-1]
    logger.info(f"Processing video: {video_path}")

    # Initialize silence trimmer
    trimmer = SilenceTrimmer()
    
    # Process the video
    output_path = trimmer.process_video(str(video_path))
    
    if output_path:
        logger.info(f"Successfully created trimmed video: {output_path}")
        # Add a special completion message that will be caught by the formatter
        logger.info("Completed: Step 1.5: Trim silence from video")
    else:
        logger.error("Failed to create trimmed video")
        sys.exit(1)

if __name__ == "__main__":
    main() 