import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from modules.subtitle_clipper import create_shorts_from_srt
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    """Get the project root directory"""
    return Path(__file__).parent.parent

def main():
    # Get project root and set up paths
    project_root = get_project_root()
    output_dir = project_root / "output"
    shorts_output_dir = output_dir / "shorts"
    subtitles_dir = output_dir / "subtitles"

    # Get the most recent video file from the output directory
    video_files = list(output_dir.glob("*_with_subs.mp4"))
    if not video_files:
        raise FileNotFoundError("No processed video found in output directory")
    
    # Use the most recent video file
    video_path = video_files[-1]
    video_name = video_path.stem.replace("_with_subs", "")

    # Get subtitle path
    srt_path = subtitles_dir / f"{video_name}.srt"
    if not srt_path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {srt_path}")

    # Keywords to look for in subtitles
    keywords = [
        "funny", "lol", "crazy", "omg", "joke", "laugh",
        "busted", "i'm dead", "what", "insane", "wow",
        "amazing", "unbelievable", "holy", "damn"
    ]

    # Create shorts
    clip_paths = create_shorts_from_srt(
        video_path=str(video_path),
        srt_path=str(srt_path),
        keywords=keywords,
        output_dir=str(shorts_output_dir),
        min_duration=15,
        max_duration=20
    )

    logger.info(f"Created {len(clip_paths)} shorts:")
    for path in clip_paths:
        logger.info(f"- {path}")

if __name__ == "__main__":
    main()
