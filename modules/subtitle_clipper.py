import os
from pathlib import Path
import subprocess
import pysrt
import json
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

def parse_srt(srt_path: Path) -> List[Dict[str, Any]]:
    """
    Parse an SRT file and return a list of subtitle segments with timing information.
    
    Args:
        srt_path: Path to the SRT file
        
    Returns:
        List of dictionaries containing subtitle information
    """
    subs = pysrt.open(str(srt_path))
    segments = []
    
    for sub in subs:
        segment = {
            'start': sub.start.ordinal / 1000,  # Convert to seconds
            'end': sub.end.ordinal / 1000,
            'text': sub.text,
            'index': sub.index
        }
        segments.append(segment)
    
    return segments

def find_clips_from_srt(
    srt_path: Path,
    keywords: List[str],
    min_duration: int = 15,
    max_duration: int = 30,
    padding: int = 2
) -> List[Dict[str, Any]]:
    """
    Find interesting clips from an SRT file based on scoring and keywords.
    
    Args:
        srt_path: Path to the SRT file
        keywords: List of keywords to look for
        min_duration: Minimum duration of clips in seconds
        max_duration: Maximum duration of clips in seconds
        padding: Number of seconds to add before and after the clip
        
    Returns:
        List of dictionaries containing clip information
    """
    # Load scoring data
    scoring_path = srt_path.with_suffix('.json')
    if not scoring_path.exists():
        raise FileNotFoundError(f"Scoring data not found: {scoring_path}")
    
    with open(scoring_path, 'r', encoding='utf-8') as f:
        scoring_data = json.load(f)
    
    segments = scoring_data['segments']
    clips = []
    max_overlap = 5  # Maximum overlap between clips in seconds
    max_extension = 5  # Maximum extension allowed beyond max_duration
    
    # Get total video duration from the last segment
    total_duration = segments[-1]['end'] if segments else 0
    
    def calculate_clip_score(clip_segments):
        """Calculate a score for a potential clip based on its segments."""
        if not clip_segments:
            return 0
        
        # Average score of all segments
        avg_score = sum(s['score'] for s in clip_segments) / len(clip_segments)
        
        # Bonus for keyword matches
        keyword_matches = sum(1 for s in clip_segments if any(k.lower() in s['text'].lower() for k in keywords))
        keyword_bonus = min(0.2, keyword_matches * 0.05)  # Up to 20% bonus for keywords
        
        return avg_score + keyword_bonus
    
    def ensure_min_duration(start_time: float, end_time: float, segments: List[Dict]) -> tuple:
        """Helper function to ensure a clip meets minimum duration"""
        duration = end_time - start_time
        if duration < min_duration:
            # Calculate how much we need to extend
            needed_extension = min_duration - duration
            # Try to extend both sides equally
            start_time = max(0, start_time - needed_extension/2)
            end_time = min(total_duration, end_time + needed_extension/2)
            # If we hit the boundaries, extend more on the other side
            if start_time == 0:
                end_time = min(total_duration, start_time + min_duration)
            elif end_time == total_duration:
                start_time = max(0, end_time - min_duration)
        return start_time, end_time, segments

    # Create a sliding window to find potential clips
    window_size = max_duration  # Maximum window size
    step_size = min_duration // 2  # Half of minimum duration for overlap
    
    for start_idx in range(0, len(segments)):
        current_segments = []
        current_duration = 0
        
        # Build a clip starting from this segment
        for i in range(start_idx, len(segments)):
            segment = segments[i]
            segment_duration = segment['end'] - segment['start']
            
            # If adding this segment would exceed max duration, stop
            if current_duration + segment_duration > window_size:
                break
                
            current_segments.append(segment)
            current_duration += segment_duration
        
        # If we have enough segments, calculate score
        if current_segments and current_duration >= min_duration:
            score = calculate_clip_score(current_segments)
            
            # Lower the threshold to create more clips
            if score > 0.3:  # Reduced from 0.5 to 0.3
                start_time = max(0, current_segments[0]['start'] - padding)
                end_time = current_segments[-1]['end'] + padding
                
                # Ensure minimum duration
                start_time, end_time, _ = ensure_min_duration(start_time, end_time, current_segments)
                
                # Handle maximum duration
                duration = end_time - start_time
                if duration > max_duration + max_extension:
                    trim_amount = (duration - (max_duration + max_extension)) / 2
                    start_time += trim_amount
                    end_time -= trim_amount
                
                # Check if this clip overlaps too much with existing clips
                is_overlapping = False
                for existing_clip in clips:
                    overlap = min(end_time, existing_clip['end']) - max(start_time, existing_clip['start'])
                    if overlap > max_overlap:
                        is_overlapping = True
                        break
                
                if not is_overlapping:
                    clips.append({
                        'start': start_time,
                        'end': end_time,
                        'text': ' '.join(s['text'] for s in current_segments),
                        'score': score
                    })
    
    # Sort clips by start time instead of score
    clips.sort(key=lambda x: x['start'])
    
    return clips

def create_shorts_from_srt(
    video_path: Path,
    srt_path: Path,
    keywords: List[str],
    output_dir: Path,
    min_duration: int = 15,
    max_duration: int = 30,
    padding: int = 2,
    output_prefix: Optional[str] = None
) -> List[Path]:
    """
    Create short video clips based on subtitle content containing specific keywords.
    
    Args:
        video_path: Path to the source video file
        srt_path: Path to the SRT subtitle file
        keywords: List of keywords to look for in subtitles
        output_dir: Directory to save the output clips
        min_duration: Minimum duration of clips in seconds
        max_duration: Maximum duration of clips in seconds
        padding: Number of seconds to add before and after the clip
        output_prefix: Optional prefix for output filenames
        
    Returns:
        List of paths to the created video clips
    """
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find clips using the find_clips_from_srt function
    clips = find_clips_from_srt(
        srt_path=srt_path,
        keywords=keywords,
        min_duration=min_duration,
        max_duration=max_duration,
        padding=padding
    )
    
    if not clips:
        logger.warning("No suitable clips found in the video")
        return []
    
    # Get video name for output files
    video_name = video_path.stem
    prefix = output_prefix or video_name
    
    # Create clips
    clip_paths = []
    for i, clip in enumerate(clips):
        # Generate output path
        output_path = output_dir / f"{prefix}_short_{i+1}.mp4"
        
        # Log clip number before processing
        logger.info(f"Processing clip {i+1}/{len(clips)}: {output_path}")
        logger.info(f"Clip score: {clip['score']:.2f}")
        
        # Create the clip using FFmpeg
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', str(video_path),
                '-ss', str(clip['start']),
                '-to', str(clip['end']),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                str(output_path)
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Check if the created clip is too small (less than 1MB)
            if output_path.stat().st_size < 1024 * 1024:  # 1MB in bytes
                logger.warning(f"Clip {i+1} is too small ({output_path.stat().st_size / 1024:.1f}KB), removing it")
                output_path.unlink()
                continue
                
            clip_paths.append(output_path)
            logger.info(f"Created clip: {output_path}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error creating clip {i+1}: {e.stderr.decode()}")
            continue
    
    # Log total number of shorts created
    logger.info(f"Successfully created {len(clip_paths)} shorts from video: {video_name}")
    # Add a special completion message that will be caught by the formatter
    logger.info(f"Completed: Step 2: Create shorts from full video (created {len(clip_paths)} shorts)")
    
    return clip_paths 