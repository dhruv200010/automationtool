"""
Script to generate YouTube titles for shorts videos using their subtitle content
"""
import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import pysrt
from modules.title_generator import TitleGenerator
from modules.subtitle_clipper import parse_srt, find_clips_from_srt
import logging

logger = logging.getLogger(__name__)

class ShortsTitleGenerator:
    def __init__(self):
        self.title_generator = TitleGenerator()
        self.titles: Dict[str, Tuple[str, List[str], str]] = {}  # Store video_path: (title, hashtags, description) mapping
        self.metadata_dir = Path("output/metadata")
        self.metadata_dir.mkdir(exist_ok=True)

    def get_subtitle_content_for_timestamps(self, subtitle_path: str, start_time: float, end_time: float) -> str:
        """Get subtitle content for a specific time range"""
        try:
            logger.info(f"\nReading subtitle file: {subtitle_path}")
            logger.info(f"Time range: {start_time:.2f}s - {end_time:.2f}s")
            
            if not os.path.exists(subtitle_path):
                logger.error(f"Error: Subtitle file not found: {subtitle_path}")
                return ""
                
            subs = pysrt.open(subtitle_path)
            # Convert times to milliseconds
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            logger.info(f"Looking for subtitles between {start_ms}ms and {end_ms}ms")
            
            # Get subtitles that fall within the time range
            relevant_subs = []
            for sub in subs:
                sub_start = sub.start.ordinal
                sub_end = sub.end.ordinal
                
                # Check if subtitle overlaps with our time range
                if (sub_start <= end_ms and sub_end >= start_ms):
                    relevant_subs.append(sub.text)
                    logger.info(f"Found subtitle: {sub.text}")
            
            content = " ".join(relevant_subs)
            if not content:
                logger.warning("Warning: No subtitles found in the specified time range")
            else:
                logger.info(f"Total subtitle content: {content[:100]}...")
            
            return content
        except Exception as e:
            logger.error(f"Error reading subtitle file {subtitle_path}: {str(e)}")
            return ""

    def safe_encode(self, text: str) -> str:
        """Safely encode text for console output"""
        return text.encode(sys.stdout.encoding, errors='ignore').decode()

    def save_metadata(self, video_path: str, title: str, hashtags: List[str], description: str, index: int):
        """Save metadata for a single short"""
        metadata = {
            "title": title,
            "hashtags": hashtags,
            "description": description,
            "video_path": str(video_path),
            "index": index
        }
        
        metadata_file = self.metadata_dir / f"short_{index+1}.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def generate_title_for_video(self, video_path: str, subtitle_path: str, start_time: float, end_time: float) -> Tuple[str, List[str], str]:
        """Generate title, hashtags, and description for a single video using its corresponding subtitle content"""
        logger.info(f"\nProcessing video: {os.path.basename(video_path)}")
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

    def process_all_shorts(self, shorts_dir: str, subtitles_dir: str, video_path: str):
        """Process all shorts videos and generate titles using the same timestamps as shorts creation"""
        logger.info(f"Current Working Directory: {os.getcwd()}")
        
        shorts_path = Path(shorts_dir)
        subtitles_path = Path("output/subtitles")  # Changed to use output/subtitles directory

        # Get all video files
        video_files = sorted(list(shorts_path.glob("*.mp4")))
        logger.info(f"Found video files in {shorts_dir}: {[str(f) for f in video_files]}")
        
        if not video_files:
            logger.error(f"No video files found in {shorts_dir}")
            return

        logger.info(f"Found {len(video_files)} video files to process")

        # Get the video name from the input video path
        video_name = Path(video_path).stem.replace("_with_subs", "")
        subtitle_file = subtitles_path / f"{video_name}.srt"
        
        logger.info(f"Looking for subtitle file: {subtitle_file}")
        logger.info(f"Available subtitle files: {list(subtitles_path.glob('*.srt'))}")
        
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
            str(subtitle_file),
            keywords,
            min_duration=15,
            max_duration=20
        )
        logger.info(f"Found {len(clip_ranges)} clip ranges")

        # Process each video with its corresponding timestamp
        for i, video_file in enumerate(video_files):
            logger.info(f"Processing video {i+1}/{len(video_files)}: {video_file}")
            
            # Get the clip range for this video
            if i < len(clip_ranges):
                clip = clip_ranges[i]
                # Generate title, hashtags, and description using the corresponding subtitle content
                title, hashtags, description = self.generate_title_for_video(
                    str(video_file), 
                    str(subtitle_file), 
                    clip['start'], 
                    clip['end']
                )
                if title:
                    self.titles[str(video_file)] = (title, hashtags, description)
                    # Save metadata for this short
                    self.save_metadata(str(video_file), title, hashtags, description, i)
            else:
                logger.warning(f"No clip range found for video {video_file}, skipping title generation")

        # Save titles to JSON file
        self.save_titles()

    def save_titles(self):
        """Save generated titles, hashtags, and descriptions to a JSON file"""
        output_file = str(Path("output") / "shorts_titles.json")
        # Convert the titles dictionary to a format that can be serialized to JSON
        serializable_titles = {
            k: {"title": v[0], "hashtags": v[1], "description": v[2]} for k, v in self.titles.items()
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(serializable_titles, f, indent=2, ensure_ascii=False)
        logger.info(f"\nTitles, hashtags, and descriptions saved to {output_file}")

def main():
    # Initialize generator
    generator = ShortsTitleGenerator()
    
    # Get the most recent video file from the output directory
    output_dir = Path("output")
    video_files = list(output_dir.glob("*_with_subs.mp4"))
    video_files.sort(key=os.path.getmtime)
    
    logger.info(f"Detected video files: {[str(f) for f in video_files]}")
    
    if not video_files:
        raise FileNotFoundError("No processed video found in output directory")
    
    # Use the most recent video file
    video_path = str(video_files[-1])
    logger.info(f"Using video: {video_path}")
    
    # Process all shorts
    generator.process_all_shorts(
        shorts_dir="output/shorts",
        subtitles_dir="subtitles",
        video_path=video_path
    )

if __name__ == "__main__":
    main() 