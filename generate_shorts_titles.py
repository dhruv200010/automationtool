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

class ShortsTitleGenerator:
    def __init__(self):
        self.title_generator = TitleGenerator()
        self.titles: Dict[str, Tuple[str, List[str]]] = {}  # Store video_path: (title, hashtags) mapping
        self.metadata_dir = Path("output/metadata")
        self.metadata_dir.mkdir(exist_ok=True)

    def get_subtitle_content_for_timestamps(self, subtitle_path: str, start_time: float, end_time: float) -> str:
        """Get subtitle content for a specific time range"""
        try:
            print(f"\nReading subtitle file: {subtitle_path}")
            print(f"Time range: {start_time:.2f}s - {end_time:.2f}s")
            
            if not os.path.exists(subtitle_path):
                print(f"Error: Subtitle file not found: {subtitle_path}")
                return ""
                
            subs = pysrt.open(subtitle_path)
            # Convert times to milliseconds
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            print(f"Looking for subtitles between {start_ms}ms and {end_ms}ms")
            
            # Get subtitles that fall within the time range
            relevant_subs = []
            for sub in subs:
                sub_start = sub.start.ordinal
                sub_end = sub.end.ordinal
                
                # Check if subtitle overlaps with our time range
                if (sub_start <= end_ms and sub_end >= start_ms):
                    relevant_subs.append(sub.text)
                    print(f"Found subtitle: {sub.text}")
            
            content = " ".join(relevant_subs)
            if not content:
                print("Warning: No subtitles found in the specified time range")
            else:
                print(f"Total subtitle content: {content[:100]}...")
            
            return content
        except Exception as e:
            print(f"Error reading subtitle file {subtitle_path}: {str(e)}")
            return ""

    def safe_encode(self, text: str) -> str:
        """Safely encode text for console output"""
        return text.encode(sys.stdout.encoding, errors='ignore').decode()

    def save_metadata(self, video_path: str, title: str, hashtags: List[str], index: int):
        """Save metadata for a single short"""
        metadata = {
            "title": title,
            "hashtags": hashtags,
            "video_path": str(video_path),
            "index": index
        }
        
        metadata_file = self.metadata_dir / f"short_{index+1}.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def generate_title_for_video(self, video_path: str, subtitle_path: str, start_time: float, end_time: float) -> Tuple[str, List[str]]:
        """Generate title and hashtags for a single video using its corresponding subtitle content"""
        print(f"\nProcessing video: {os.path.basename(video_path)}")
        print(f"Time range: {start_time:.2f}s - {end_time:.2f}s")
        
        # Get subtitle content for the specific time range
        subtitle_content = self.get_subtitle_content_for_timestamps(subtitle_path, start_time, end_time)
        if not subtitle_content:
            print(f"No subtitle content found for {video_path} between {start_time}s and {end_time}s")
            return "", []

        # Generate title and hashtags using the subtitle content
        result = self.title_generator.generate_title_and_hashtags(subtitle_content)
        if result:
            title, hashtags = result
            safe_title = self.safe_encode(title)
            print(f"Generated title: {safe_title}")
            print(f"Generated hashtags: {' '.join(hashtags)}")
            return title, hashtags
        else:
            print(f"Failed to generate title for {video_path}")
            return "", []

    def process_all_shorts(self, shorts_dir: str, subtitles_dir: str, video_path: str):
        """Process all shorts videos and generate titles using the same timestamps as shorts creation"""
        shorts_path = Path(shorts_dir)
        subtitles_path = Path(subtitles_dir)

        # Get all video files
        video_files = sorted(list(shorts_path.glob("*.mp4")))
        
        if not video_files:
            print(f"No video files found in {shorts_dir}")
            return

        print(f"Found {len(video_files)} video files to process")

        # Get the video name from the input video path
        video_name = Path(video_path).stem.replace("_with_subs", "")
        subtitle_file = subtitles_path / f"{video_name}.srt"
        
        if not subtitle_file.exists():
            print(f"Subtitle file {subtitle_file} not found in {subtitles_dir}")
            return

        # Get the same clip ranges used to create the shorts
        segments = parse_srt(str(subtitle_file))
        keywords = [
            "funny", "lol", "crazy", "omg", "joke", "laugh",
            "busted", "i'm dead", "what", "insane", "wow",
            "amazing", "unbelievable", "holy", "damn"
        ]
        clip_ranges = find_clips_from_srt(
            segments,
            keywords,
            min_duration=15,
            max_duration=20
        )

        if len(video_files) != len(clip_ranges):
            print(f"Number of videos ({len(video_files)}) doesn't match number of clip ranges ({len(clip_ranges)})")
            return

        # Process each video with its corresponding timestamp
        for i, (video_file, (start_time, end_time)) in enumerate(zip(video_files, clip_ranges)):
            # Generate title and hashtags using the corresponding subtitle content
            title, hashtags = self.generate_title_for_video(str(video_file), str(subtitle_file), start_time, end_time)
            if title:
                self.titles[str(video_file)] = (title, hashtags)
                # Save metadata for this short
                self.save_metadata(str(video_file), title, hashtags, i)

        # Save titles to JSON file
        self.save_titles()

    def save_titles(self):
        """Save generated titles and hashtags to a JSON file"""
        output_file = "shorts_titles.json"
        # Convert the titles dictionary to a format that can be serialized to JSON
        serializable_titles = {
            k: {"title": v[0], "hashtags": v[1]} for k, v in self.titles.items()
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(serializable_titles, f, indent=2, ensure_ascii=False)
        print(f"\nTitles and hashtags saved to {output_file}")

def main():
    # Initialize generator
    generator = ShortsTitleGenerator()
    
    # Get the most recent video file from the output directory
    output_dir = Path("output")
    video_files = list(output_dir.glob("*_with_subs.mp4"))
    if not video_files:
        raise FileNotFoundError("No processed video found in output directory")
    
    # Use the most recent video file
    video_path = str(video_files[-1])
    
    # Process all shorts
    generator.process_all_shorts(
        shorts_dir="output/shorts",
        subtitles_dir="subtitles",
        video_path=video_path
    )

if __name__ == "__main__":
    main() 