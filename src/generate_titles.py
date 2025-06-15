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
        """Initialize the title generator with paths"""
        # Get the root directory (parent of src)
        self.root_dir = Path(__file__).parent.parent
        
        # Load and normalize output folder from config
        config_path = self.root_dir / "config" / "master_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            self.output_root = Path(config['output_folder']).expanduser().resolve()
        
        # Initialize title generator
        self.title_generator = TitleGenerator()
        self.titles = {}
        
        # Load existing titles if available
        self.titles_file = self.output_root / "titles.json"
        if self.titles_file.exists():
            with open(self.titles_file, 'r', encoding='utf-8') as f:
                self.titles = json.load(f)
        
        self.metadata_dir = self.output_root / "metadata"
        self.metadata_dir.mkdir(exist_ok=True)

    def safe_encode(self, text: str) -> str:
        """Safely encode text for logging"""
        return text.encode('utf-8', errors='replace').decode('utf-8')

    def get_subtitle_content_for_timestamps(self, subtitle_path: Path, start_time: float, end_time: float) -> str:
        """Get subtitle content for a specific time range"""
        try:
            subs = pysrt.open(str(subtitle_path))
            content = []
            for sub in subs:
                sub_start = sub.start.ordinal / 1000
                sub_end = sub.end.ordinal / 1000
                if sub_start <= end_time and sub_end >= start_time:
                    content.append(sub.text)
            return " ".join(content)
        except Exception as e:
            logger.error(f"Error reading subtitles: {str(e)}")
            return ""

    def save_metadata(self, video_path: Path, title: str, hashtags: List[str], description: str, index: int, video_name: str):
        """Save metadata for a single short"""
        # Strip quotes from title and description
        title = title.strip('"').strip("'")  # Remove both single and double quotes
        description = description.strip('"').strip("'")  # Remove both single and double quotes
        
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

    def generate_title_for_video(self, video_path: Path, subtitle_path: Path, start_time: float, end_time: float, clip_number: int = 0, total_clips: int = 0) -> Tuple[str, List[str], str]:
        """Generate title, hashtags, and description for a single video using its corresponding subtitle content"""
        clip_info = f"\n{'='*50}\n📋 Processing Clip {clip_number}/{total_clips} - {video_path.name}\n{'='*50}" if total_clips > 0 else ""
        print(clip_info)
        
        # Get subtitle content for the specific time range
        subtitle_content = self.get_subtitle_content_for_timestamps(subtitle_path, start_time, end_time)
        if not subtitle_content:
            print(f"Error: No subtitle content found for {video_path} between {start_time}s and {end_time}s")
            return "", [], ""

        # Generate title, hashtags, and description using the subtitle content
        result = self.title_generator.generate_title_and_hashtags(subtitle_content)
        if result:
            title, hashtags, description = result
            safe_title = self.safe_encode(title)
            print(f"Generated title: {safe_title}")
            print(f"Generated hashtags: {' '.join(hashtags)}")
            print(f"Generated description: {description}")
            return title, hashtags, description
        else:
            print(f"Error: Failed to generate title for {video_path}")
            return "", [], ""

    def process_all_shorts(self, shorts_dir: Path, subtitles_dir: Path, video_path: Path):
        """Process all shorts videos and generate titles using the scoring data"""
        print(f"Current Working Directory: {Path.cwd()}")
        
        # Get the video name from the input video path
        video_name = video_path.stem.replace("_with_subs_trimmed", "")
        print(f"Processing video: {video_name}")
        
        # Filter only shorts matching the current video's name
        video_files = list(shorts_dir.glob(f"{video_name}_short_*.mp4"))
        # Sort by clip number instead of filename
        video_files.sort(key=lambda x: int(x.stem.split('_')[-1]))
        print(f"Found video files in {shorts_dir}: {[str(f) for f in video_files]}")
        
        if not video_files:
            print(f"Error: No video files found in {shorts_dir}")
            return

        total_clips = len(video_files)
        print(f"Found {total_clips} video files to process")

        # Get the scoring data JSON file
        scoring_file = subtitles_dir / f"{video_name}.json"
        print(f"Looking for scoring data file: {scoring_file}")
        
        if not scoring_file.exists():
            print(f"Warning: Scoring data file {scoring_file} not found")
            print("Checking for scoring data in output directory...")
            # Try looking in the output directory
            scoring_file = self.output_root / f"{video_name}.json"
            if not scoring_file.exists():
                print(f"Error: Scoring data file {scoring_file} not found")
                return
            print(f"Found scoring data file: {scoring_file}")

        # Load scoring data
        try:
            with open(scoring_file, 'r', encoding='utf-8') as f:
                scoring_data = json.load(f)
        except Exception as e:
            print(f"Error loading scoring data: {str(e)}")
            return
        
        # Get the segments with their timestamps
        segments = scoring_data.get('segments', [])
        if not segments:
            print(f"Error: No segments found in scoring data")
            return
        
        # Process each video with its corresponding timestamp
        for i, video_file in enumerate(video_files):
            # Get the clip number from the filename
            try:
                clip_num = int(video_file.stem.split('_')[-1]) - 1  # Convert to 0-based index
            except (ValueError, IndexError):
                print(f"Warning: Could not determine clip number from {video_file}, skipping")
                continue
            
            # Find the corresponding segment in the scoring data
            if clip_num < len(segments):
                segment = segments[clip_num]
                # Generate title, hashtags, and description using the corresponding subtitle content
                title, hashtags, description = self.generate_title_for_video(
                    video_file, 
                    subtitles_dir / f"{video_name}.srt", 
                    segment['start'], 
                    segment['end'],
                    clip_num + 1,  # Clip number (1-based)
                    total_clips  # Total number of clips
                )
                if title:
                    self.titles[str(video_file)] = (title, hashtags, description)
                    # Save metadata for this short with unique filename
                    self.save_metadata(video_file, title, hashtags, description, clip_num, video_name)
            else:
                print(f"Warning: No scoring data found for clip {clip_num + 1}, skipping title generation")

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
    """Main function to generate titles for all shorts"""
    try:
        # Initialize the title generator
        generator = ShortsTitleGenerator()
        
        # Get processed video files from the processed directory
        processed_dir = generator.output_root / "processed"
        if not processed_dir.exists():
            raise FileNotFoundError(f"Processed directory not found: {processed_dir}")
            
        # Get all processed videos sorted by modification time
        video_files = sorted(
            processed_dir.glob("*_with_subs_trimmed.mp4"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        if not video_files:
            print(f"Warning: No processed videos found in {processed_dir}")
            print("Checking for videos in output directory...")
            # Try looking in the output directory directly
            video_files = sorted(
                generator.output_root.glob("*_with_subs_trimmed.mp4"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            if not video_files:
                raise FileNotFoundError(f"No processed videos found in {generator.output_root}")
            
        print(f"Found {len(video_files)} processed videos")
        for video in video_files:
            print(f"Processing video: {video.name}")
            
            # Get the corresponding subtitle file
            subtitles_dir = generator.output_root / "subtitles"
            if not subtitles_dir.exists():
                print(f"Warning: Subtitles directory not found: {subtitles_dir}")
                print("Using output directory for subtitles...")
                subtitles_dir = generator.output_root
                
            # Process all shorts for this video
            shorts_dir = generator.output_root / "shorts"
            if not shorts_dir.exists():
                print(f"Warning: Shorts directory not found: {shorts_dir}")
                print("Using output directory for shorts...")
                shorts_dir = generator.output_root
                
            generator.process_all_shorts(shorts_dir, subtitles_dir, video)
            
        print("Title generation completed successfully!")
        
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        raise

if __name__ == "__main__":
    main() 