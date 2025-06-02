import re
from pathlib import Path
from typing import List, Tuple, Dict
from moviepy.video.io.VideoFileClip import VideoFileClip

def srt_to_seconds(srt_time: str) -> float:
    """Convert SRT timestamp to seconds."""
    h, m, s = srt_time.split(":")
    s, ms = s.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms)/1000

def parse_srt(file_path: str) -> List[Dict]:
    """Parse SRT file and return list of segments with start, end times and text."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r"\n\n+", content.strip())
    segments = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            time_line = lines[1]
            start_str, end_str = time_line.split(" --> ")
            start = srt_to_seconds(start_str)
            end = srt_to_seconds(end_str)
            text = " ".join(lines[2:])
            segments.append({"start": start, "end": end, "text": text})
    
    return segments

def find_clips_from_srt(
    segments: List[Dict],
    keywords: List[str],
    min_duration: float = 15,
    max_duration: float = 20,
    padding_before: float = 2,
    padding_after: float = 2
) -> List[Tuple[float, float]]:
    """Find clip ranges based on keyword matches in subtitle segments."""
    clips = []

    for seg in segments:
        if any(k.lower() in seg['text'].lower() for k in keywords):
            # Calculate clip start and end with padding
            start = max(0, seg['start'] - padding_before)
            end = seg['end'] + padding_after
            
            # If clip is too short, extend it backward
            if end - start < min_duration:
                start = max(0, end - min_duration)
            
            # If clip is too long, cap it at max_duration
            if end - start > max_duration:
                end = start + max_duration
            
            clips.append((start, end))

    return clips

def save_clips(
    video_path: str,
    clip_ranges: List[Tuple[float, float]],
    output_dir: str = "output/clips"
) -> List[str]:
    """Save video clips based on the provided time ranges."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    clip_paths = []
    
    with VideoFileClip(video_path) as base:
        duration = base.duration
        
        for i, (start, end) in enumerate(clip_ranges):
            # Ensure end time doesn't exceed video duration
            end = min(end, duration)
            
            # If clip is too short after capping, extend backward
            if end - start < 15:  # minimum duration
                start = max(0, end - 15)
            
            out_path = f"{output_dir}/short_{i+1}.mp4"
            subclip = base.subclipped(start, end)
            subclip.write_videofile(
                out_path,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="ultrafast"
            )
            clip_paths.append(out_path)
    
    return clip_paths

def create_shorts_from_srt(
    video_path: str,
    srt_path: str,
    keywords: List[str],
    output_dir: str = "output/clips",
    min_duration: float = 15,
    max_duration: float = 20
) -> List[str]:
    """Main function to create shorts from video using SRT file."""
    # Parse SRT file
    segments = parse_srt(srt_path)
    
    # Find clip ranges
    clip_ranges = find_clips_from_srt(
        segments,
        keywords,
        min_duration=min_duration,
        max_duration=max_duration
    )
    
    # Save clips
    return save_clips(video_path, clip_ranges, output_dir) 