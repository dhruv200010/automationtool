from modules.subtitle_clipper import create_shorts_from_srt
import os
from pathlib import Path

# Example usage
if __name__ == "__main__":
    # Get the most recent video file from the output directory
    output_dir = Path("output")
    video_files = list(output_dir.glob("*_with_subs.mp4"))
    if not video_files:
        raise FileNotFoundError("No processed video found in output directory")
    
    # Use the most recent video file
    video_path = str(video_files[-1])
    video_name = Path(video_path).stem.replace("_with_subs", "")

    # ✅ Corrected subtitle path
    srt_path = str(Path("output/subtitles") / f"{video_name}.srt")
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"Subtitle file not found: {srt_path}")

    # Output shorts directory
    shorts_output_dir = "output/shorts"

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
        max_duration=20
    )

    print(f"Created {len(clip_paths)} shorts:")
    for path in clip_paths:
        print(f"- {path}")
