import os
import sys
import json
from pathlib import Path
import logging

# Add the project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from modules.subtitle_clipper import create_shorts_from_srt
from modules.transcription import TranscriptionHandler

logger = logging.getLogger(__name__)

def main():
    # Load and normalize output folder from config
    config_path = project_root / "config" / "master_config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        output_root = Path(config['output_folder']).expanduser().resolve()
    
    # Set up paths
    shorts_output_dir = output_root / "shorts"
    subtitles_dir = output_root / "subtitles"
    processed_dir = output_root / "processed"
    shorts_output_dir.mkdir(parents=True, exist_ok=True)
    subtitles_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Get the most recent trimmed video file from the processed directory
    video_files = list(processed_dir.glob("*_trimmed.mp4"))
    if not video_files:
        raise FileNotFoundError("No trimmed video found in processed directory")
    
    # Use the most recent video file
    video_path = video_files[-1]
    video_name = video_path.stem.replace("_with_subs_trimmed", "")

    # Get subtitle path
    srt_path = subtitles_dir / f"{video_name}.srt"
    
    # If SRT file doesn't exist or scoring data is missing, generate it
    if not srt_path.exists() or not srt_path.with_suffix('.json').exists():
        logger.info("Generating transcription and scoring data...")
        handler = TranscriptionHandler()
        srt_path = handler.transcribe_video(video_path)
        logger.info(f"Generated transcription and scoring data: {srt_path}")

    # Keywords to look for in subtitles
    keywords = [
        "funny", "lol", "crazy", "omg", "joke", "laugh",
        "busted", "i'm dead", "what", "insane", "wow",
        "amazing", "unbelievable", "holy", "damn"
    ]

    # Create shorts
    clip_paths = create_shorts_from_srt(
        video_path=video_path,
        srt_path=srt_path,
        keywords=keywords,
        output_dir=shorts_output_dir,
        min_duration=15,
        max_duration=30,
        padding=2,
        output_prefix=f"{video_name}_short_"  # Add unique prefix for each video
    )

    if clip_paths:
        logger.info(f"Successfully created {len(clip_paths)} shorts")
        for path in clip_paths:
            logger.info(f"Created short: {path}")
    else:
        logger.warning("No shorts were created")

if __name__ == "__main__":
    main()
