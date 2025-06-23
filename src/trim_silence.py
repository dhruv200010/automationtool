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
    if len(sys.argv) != 2:
        print("Usage: python src/trim_silence.py <video_path>")
        sys.exit(1)

    video_path = Path(sys.argv[1])
    
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        sys.exit(1)

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