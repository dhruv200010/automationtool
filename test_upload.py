from modules.upload_youtube import upload_to_youtube
from modules.schedule_config import ScheduleConfig
import datetime

def upload_videos(video_paths):
    """
    Upload multiple videos with scheduled publishing times.
    
    Args:
        video_paths: List of paths to video files
    """
    # Initialize schedule config
    config = ScheduleConfig()
    
    # Get schedule for all videos
    schedule = config.get_schedule_for_videos(len(video_paths))
    
    # Validate schedule
    if not config.validate_schedule(schedule):
        print("Warning: Schedule doesn't meet requirements")
        return
    
    # Upload each video with its scheduled time
    for i, (video_path, publish_time) in enumerate(zip(video_paths, schedule)):
        print(f"\nProcessing video {i+1}/{len(video_paths)}")
        print(f"Scheduled for: {publish_time.strftime('%Y-%m-%d %H:%M')}")
        
        # Upload the video
        video_id = upload_to_youtube(
            video_path=video_path,
            title=f"Video {i+1}",
            description=f"Automatically scheduled video {i+1}",
            tags=["scheduled", "automated", f"video{i+1}"],
            publish_time=publish_time.isoformat() + "Z"
        )
        
        if video_id:
            print(f"✅ Video {i+1} uploaded successfully!")
            print(f"View it here: https://youtube.com/watch?v={video_id}")
        else:
            print(f"❌ Failed to upload video {i+1}")

if __name__ == "__main__":
    # Example video paths (replace with your actual video paths)
    video_paths = [
        "output/short_0.mp4",
        "output/short_1.mp4",
        "output/short_2.mp4",
        "output/short_3.mp4",
        "output/short_4.mp4"
    ]
    
    upload_videos(video_paths) 