"""
Script to generate YouTube titles for shorts videos using their subtitle content
"""
import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import pysrt

# Add the project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from modules.title_generator import TitleGenerator
from modules.subtitle_clipper import parse_srt, find_clips_from_srt
import logging

logger = logging.getLogger(__name__)

class ShortsTitleGenerator:
    def __init__(self):
        self.title_generator = TitleGenerator()
        self.titles: Dict[str, Tuple[str, List[str], str]] = {}  # Store video_path: (title, hashtags, description) mapping
        
        # Load and normalize output folder from config
        config_path = project_root / "config" / "master_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            self.output_root = Path(config['output_folder']).expanduser().resolve()
        
        self.metadata_dir = self.output_root / "metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def safe_encode(self, text: str) -> str:
        """Safely encode text for logging"""
        return text.encode('utf-8', errors='replace').decode('utf-8')

    def get_subtitle_content_for_timestamps(self, subtitle_path: Path, start_time: float, end_time: float) -> str:
        """Get subtitle content for a specific time range"""
        try:
            subs = pysrt.open(str(subtitle_path))
            content = []
            for sub in subs:
                if start_time <= sub.start.ordinal / 1000 <= end_time:
                    content.append(sub.text)
            return " ".join(content)
        except Exception as e:
            logger.error(f"Error reading subtitles: {str(e)}")
            return ""

    def save_metadata(self, video_path: Path, title: str, hashtags: List[str], description: str, index: int, video_name: str):
        """Save metadata for a single short"""
        metadata = {
            "title": title,
            "hashtags": hashtags,
            "description": description,
            "video_path": str(video_path),
            "index": index,
            "source_video": video_name
        }
        
        # Create a unique filename using video name and index
        metadata_file = self.metadata_dir / f"{video_name}_short_{index+1}.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved metadata to {metadata_file}")

    def generate_title_for_video(self, video_path: Path, subtitle_path: Path, start_time: float, end_time: float) -> Tuple[str, List[str], str]:
        """Generate title, hashtags, and description for a single video using its corresponding subtitle content"""
        logger.info(f"\nProcessing video: {video_path.name}")
        logger.info(f"Time range: {start_time:.2f}s - {end_time:.2f}s")
        
        # Get subtitle content for the specific time range
        subtitle_content = self.get_subtitle_content_for_timestamps(subtitle_path, start_time, end_time)
        if not subtitle_content:
            logger.error(f"No subtitle content found for {video_path} between {start_time}s and {end_time}s")
            return "", [], ""

        # Generate title, hashtags, and description using the subtitle content
        result = self.title_generator.generate_title_and_hashtags(subtitle_content)
        if result:
            title, hashtags, description = result
            safe_title = self.safe_encode(title)
            logger.info(f"Generated title: {safe_title}")
            logger.info(f"Generated hashtags: {' '.join(hashtags)}")
            logger.info(f"Generated description: {description}")
            return title, hashtags, description
        else:
            logger.error(f"Failed to generate title for {video_path}")
            return "", [], ""

    def process_all_shorts(self, shorts_dir: Path, subtitles_dir: Path, video_path: Path):
        """Process all shorts videos and generate titles using the same timestamps as shorts creation"""
        logger.info(f"Current Working Directory: {Path.cwd()}")
        
        # Get the video name from the input video path
        video_name = video_path.stem.replace("_with_subs", "")
        
        # Filter only shorts matching the current video's name
        video_files = sorted(shorts_dir.glob(f"{video_name}_short_*.mp4"))
        logger.info(f"Found video files in {shorts_dir}: {[str(f) for f in video_files]}")
        
        if not video_files:
            logger.error(f"No video files found in {shorts_dir}")
            return

        logger.info(f"Found {len(video_files)} video files to process")

        subtitle_file = subtitles_dir / f"{video_name}.srt"
        
        logger.info(f"Looking for subtitle file: {subtitle_file}")
        logger.info(f"Available subtitle files: {list(subtitles_dir.glob('*.srt'))}")
        
        if not subtitle_file.exists():
            logger.error(f"Subtitle file {subtitle_file} not found in {subtitles_dir}")
            return

        # Get the same clip ranges used to create the shorts
        keywords = [
            "funny", "lol", "crazy", "omg", "joke", "laugh",
            "busted", "i'm dead", "what", "insane", "wow",
            "amazing", "unbelievable", "holy", "damn"
        ]
        
        logger.info(f"Finding clips from SRT file: {subtitle_file}")
        clip_ranges = find_clips_from_srt(
            subtitle_file,
            keywords,
            min_duration=15,
            max_duration=20
        )
        logger.info(f"Found {len(clip_ranges)} clip ranges")

        # If no clip ranges found, try to get content from the entire video
        if not clip_ranges:
            logger.warning("No clip ranges found, attempting to get content from entire video")
            try:
                subs = pysrt.open(str(subtitle_file))
                if subs:
                    # Get content from first 20 seconds
                    content = []
                    for sub in subs:
                        if sub.start.ordinal / 1000 <= 20:  # First 20 seconds
                            content.append(sub.text)
                    if content:
                        subtitle_content = " ".join(content)
                        # Generate title for the entire content
                        title, hashtags, description = self.title_generator.generate_title_and_hashtags(subtitle_content)
                        if title:
                            for i, video_file in enumerate(video_files):
                                self.titles[str(video_file)] = (title, hashtags, description)
                                self.save_metadata(video_file, title, hashtags, description, i, video_name)
                            return
            except Exception as e:
                logger.error(f"Error processing entire video: {str(e)}")

        # Process each video with its corresponding timestamp
        for i, video_file in enumerate(video_files):
            logger.info(f"Processing video {i+1}/{len(video_files)}: {video_file}")
            
            # Get the clip range for this video
            if i < len(clip_ranges):
                clip = clip_ranges[i]
                # Generate title, hashtags, and description using the corresponding subtitle content
                title, hashtags, description = self.generate_title_for_video(
                    video_file, 
                    subtitle_file, 
                    clip['start'], 
                    clip['end']
                )
                if title:
                    self.titles[str(video_file)] = (title, hashtags, description)
                    # Save metadata for this short with unique filename
                    self.save_metadata(video_file, title, hashtags, description, i, video_name)
            else:
                logger.warning(f"No clip range found for video {video_file}, skipping title generation")

        # Save titles to JSON file
        self.save_titles()

    def save_titles(self):
        """Save generated titles, hashtags, and descriptions to a JSON file"""
        output_file = self.output_root / "shorts_titles.json"
        # Convert the titles dictionary to a format that can be serialized to JSON
        serializable_titles = {}
        for k, v in self.titles.items():
            # Convert absolute path to relative path if it's within project root
            try:
                rel_path = str(Path(k).relative_to(self.output_root)).replace('\\', '/')
            except ValueError:
                # If path is not in project root, use it as is
                rel_path = str(Path(k)).replace('\\', '/')
            # Convert tuple to dictionary format
            title, hashtags, description = v
            serializable_titles[rel_path] = {
                "title": title,
                "hashtags": hashtags,
                "description": description,
                "uploaded": False,  # Track upload status
                "upload_date": None,  # Track when it was uploaded
                "youtube_id": None  # Store YouTube video ID after upload
            }

        # Load existing titles if file exists
        existing_titles = {}
        if output_file.exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    existing_titles = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Could not load existing titles file, starting fresh")

        # Update only new titles, preserve upload status of existing ones
        for path, data in serializable_titles.items():
            if path not in existing_titles:
                existing_titles[path] = data
            else:
                # Preserve upload status of existing titles
                data["uploaded"] = existing_titles[path].get("uploaded", False)
                data["upload_date"] = existing_titles[path].get("upload_date")
                data["youtube_id"] = existing_titles[path].get("youtube_id")
                existing_titles[path] = data

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(existing_titles, f, indent=2, ensure_ascii=False)
        logger.info(f"\nTitles, hashtags, and descriptions saved to {output_file}")

def main():
    # Initialize generator
    generator = ShortsTitleGenerator()
    
    # Get all processed video files from the output directory
    video_files = list(generator.output_root.glob("*_with_subs.mp4"))
    video_files.sort(key=lambda x: x.stat().st_mtime)
    
    logger.info(f"Detected video files: {[str(f) for f in video_files]}")
    
    if not video_files:
        raise FileNotFoundError("No processed video found in output directory")
    
    # Process each video
    for video_path in video_files:
        logger.info(f"\nProcessing video: {video_path}")
        
        # Get the corresponding subtitle file
        subtitle_path = video_path.parent / "subtitles" / f"{video_path.stem.replace('_with_subs', '')}.srt"
        if not subtitle_path.exists():
            logger.error(f"Subtitle file not found for {video_path}")
            continue
        
        # Process all shorts for this video
        generator.process_all_shorts(
            generator.output_root / "shorts",
            generator.output_root / "subtitles",
            video_path
        )

if __name__ == "__main__":
    main() 