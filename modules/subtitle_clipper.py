import os
from pathlib import Path
import subprocess
import pysrt
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
    max_duration: int = 20,
    padding: int = 2
) -> List[Dict[str, Any]]:
    """
    Find interesting clips from an SRT file based on keywords.
    
    Args:
        srt_path: Path to the SRT file
        keywords: List of keywords to look for
        min_duration: Minimum duration of clips in seconds
        max_duration: Maximum duration of clips in seconds (can be extended by 4-5 seconds)
        padding: Number of seconds to add before and after the clip
        
    Returns:
        List of dictionaries containing clip information
    """
    segments = parse_srt(srt_path)
    clips = []
    current_clip = None
    max_overlap = 5  # Maximum overlap between clips in seconds
    max_extension = 5  # Maximum extension allowed beyond max_duration
    
    # Get total video duration from the last segment
    total_duration = segments[-1]['end'] if segments else 0
    
    def ensure_min_duration(start_time: float, end_time: float, text: str) -> tuple:
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
        return start_time, end_time, text

    for i, segment in enumerate(segments):
        text = segment['text'].lower()
        if any(keyword.lower() in text for keyword in keywords):
            if current_clip is None:
                current_clip = {
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': text
                }
            else:
                # Extend current clip if it's close to the previous one and within max overlap
                if segment['start'] - current_clip['end'] < max_overlap:
                    current_clip['end'] = segment['end']
                    current_clip['text'] += f" {text}"
                else:
                    # Add padding and ensure duration limits
                    start_time = max(0, current_clip['start'] - padding)
                    end_time = current_clip['end'] + padding
                    
                    # Ensure minimum duration
                    start_time, end_time, current_clip['text'] = ensure_min_duration(
                        start_time, end_time, current_clip['text']
                    )
                    
                    # Handle maximum duration
                    duration = end_time - start_time
                    if duration > max_duration + max_extension:
                        trim_amount = (duration - (max_duration + max_extension)) / 2
                        start_time += trim_amount
                        end_time -= trim_amount
                    
                    clips.append({
                        'start': start_time,
                        'end': end_time,
                        'text': current_clip['text']
                    })
                    
                    current_clip = {
                        'start': segment['start'],
                        'end': segment['end'],
                        'text': text
                    }
    
    # Handle the last clip if it exists
    if current_clip:
        start_time = max(0, current_clip['start'] - padding)
        end_time = current_clip['end'] + padding
        
        # If this is the last clip and it's too short, try to merge it with the previous clip
        if clips:
            last_clip = clips[-1]
            combined_duration = end_time - last_clip['start']
            
            # Try to merge if the combined duration is within limits
            if combined_duration <= max_duration + max_extension:
                # Merge with previous clip
                last_clip['end'] = end_time
                last_clip['text'] += f" {current_clip['text']}"
            else:
                # If we can't merge, ensure the current clip meets minimum duration
                start_time, end_time, current_clip['text'] = ensure_min_duration(
                    start_time, end_time, current_clip['text']
                )
                
                # Handle maximum duration
                duration = end_time - start_time
                if duration > max_duration + max_extension:
                    trim_amount = (duration - (max_duration + max_extension)) / 2
                    start_time += trim_amount
                    end_time -= trim_amount
                
                clips.append({
                    'start': start_time,
                    'end': end_time,
                    'text': current_clip['text']
                })
        else:
            # If this is the only clip, ensure it meets minimum duration
            start_time, end_time, current_clip['text'] = ensure_min_duration(
                start_time, end_time, current_clip['text']
            )
            
            # Handle maximum duration
            duration = end_time - start_time
            if duration > max_duration + max_extension:
                trim_amount = (duration - (max_duration + max_extension)) / 2
                start_time += trim_amount
                end_time -= trim_amount
            
            clips.append({
                'start': start_time,
                'end': end_time,
                'text': current_clip['text']
            })
    
    # Add clips for the start and end portions if they don't exist
    if clips:
        # Add start portion if first clip doesn't start at 0
        if clips[0]['start'] > 0:
            start_time = 0
            end_time = min(clips[0]['start'], max_duration + max_extension)
            start_time, end_time, _ = ensure_min_duration(start_time, end_time, "Video Introduction")
            start_clip = {
                'start': start_time,
                'end': end_time,
                'text': "Video Introduction"
            }
            clips.insert(0, start_clip)
        
        # Add end portion if last clip doesn't end at total duration
        if clips[-1]['end'] < total_duration:
            start_time = max(clips[-1]['end'], total_duration - (max_duration + max_extension))
            end_time = total_duration
            start_time, end_time, _ = ensure_min_duration(start_time, end_time, "Video Conclusion")
            end_clip = {
                'start': start_time,
                'end': end_time,
                'text': "Video Conclusion"
            }
            clips.append(end_clip)
    
    # Final verification to ensure no clips are shorter than minimum duration
    for clip in clips:
        duration = clip['end'] - clip['start']
        if duration < min_duration:
            # Extend the clip to meet minimum duration
            needed_extension = min_duration - duration
            clip['start'] = max(0, clip['start'] - needed_extension/2)
            clip['end'] = min(total_duration, clip['end'] + needed_extension/2)
            # If we hit the boundaries, extend more on the other side
            if clip['start'] == 0:
                clip['end'] = min(total_duration, clip['start'] + min_duration)
            elif clip['end'] == total_duration:
                clip['start'] = max(0, clip['end'] - min_duration)
    
    return clips

def create_shorts_from_srt(
    video_path: Path,
    srt_path: Path,
    keywords: List[str],
    output_dir: Path,
    min_duration: int = 15,
    max_duration: int = 20,
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
    
    # Create clips
    clip_paths = []
    video_name = video_path.stem
    prefix = output_prefix or f"{video_name}_short_"
    
    for i, clip in enumerate(clips):
        # Generate output path
        output_path = output_dir / f"{prefix}{i+1}.mp4"
        
        # Log clip number before processing
        logger.info(f"Processing clip {i+1}/{len(clips)}: {output_path}")
        
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