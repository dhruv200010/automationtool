"""
Script to generate YouTube titles for shorts videos using their subtitle content
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple
import pysrt
from modules.title_generator import TitleGenerator
from modules.subtitle_clipper import parse_srt, find_clips_from_srt

class ShortsTitleGenerator:
    def __init__(self):
        self.title_generator = TitleGenerator()
        self.titles: Dict[str, str] = {}  # Store video_path: title mapping

    def get_subtitle_content_for_timestamps(self, subtitle_path: str, start_time: float, end_time: float) -> str:
        """Get subtitle content for a specific time range"""
        try:
            subs = pysrt.open(subtitle_path)
            # Convert times to milliseconds
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            # Get subtitles that fall within the time range
            relevant_subs = []
            for sub in subs:
                sub_start = sub.start.ordinal
                sub_end = sub.end.ordinal
                
                # Check if subtitle overlaps with our time range
                if (sub_start <= end_ms and sub_end >= start_ms):
                    relevant_subs.append(sub.text)
            
            return " ".join(relevant_subs)
        except Exception as e:
            print(f"Error reading subtitle file {subtitle_path}: {str(e)}")
            return ""

    def generate_title_for_video(self, video_path: str, subtitle_path: str, start_time: float, end_time: float) -> str:
        """Generate title for a single video using its corresponding subtitle content"""
        print(f"\nProcessing video: {os.path.basename(video_path)}")
        print(f"Time range: {start_time:.2f}s - {end_time:.2f}s")
        
        # Get subtitle content for the specific time range
        subtitle_content = self.get_subtitle_content_for_timestamps(subtitle_path, start_time, end_time)
        if not subtitle_content:
            print(f"⚠️ No subtitle content found for {video_path} between {start_time}s and {end_time}s")
            return ""

        # Generate title using the subtitle content
        title = self.title_generator.generate_title(subtitle_content)
        if title:
            print(f"✅ Generated title: {title}")
            return title
        else:
            print(f"❌ Failed to generate title for {video_path}")
            return ""

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

        # Use the test.srt file
        subtitle_file = subtitles_path / "test.srt"
        if not subtitle_file.exists():
            print(f"⚠️ Subtitle file test.srt not found in {subtitles_dir}")
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
            print(f"⚠️ Number of videos ({len(video_files)}) doesn't match number of clip ranges ({len(clip_ranges)})")
            return

        # Process each video with its corresponding timestamp
        for video_file, (start_time, end_time) in zip(video_files, clip_ranges):
            # Generate title using the corresponding subtitle content
            title = self.generate_title_for_video(str(video_file), str(subtitle_file), start_time, end_time)
            if title:
                self.titles[str(video_file)] = title

        # Save titles to JSON file
        self.save_titles()

    def save_titles(self):
        """Save generated titles to a JSON file"""
        output_file = "shorts_titles.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.titles, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Titles saved to {output_file}")

def main():
    # Initialize generator
    generator = ShortsTitleGenerator()
    
    # Process all shorts
    generator.process_all_shorts(
        shorts_dir="output/shorts",
        subtitles_dir="subtitles",
        video_path="output/test_with_subs.mp4"
    )

if __name__ == "__main__":
    main() 