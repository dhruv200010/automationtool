from modules.schedule_config import ScheduleConfig
from datetime import datetime, timedelta
import pytz
import os

def simulate_video_upload(video_paths):
    """
    Simulate uploading multiple videos and check their scheduling.
    
    Args:
        video_paths: List of paths to video files
    """
    # Create schedule config
    config = ScheduleConfig()
    
    print("\n=== Multiple Video Upload Test ===")
    print(f"Number of videos to schedule: {len(video_paths)}")
    print(f"Current timezone: {config.timezone.zone}")
    print(f"Current time: {config.get_current_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Get schedule for all videos
    schedule = config.get_schedule_for_videos(len(video_paths))
    
    # Print schedule details
    print("\n=== Schedule Details ===")
    print("=" * 80)
    print(f"{'Video':<10} {'Scheduled Date':<15} {'Scheduled Time (IST)':<20} {'UTC Time':<20}")
    print("-" * 80)
    
    for i, (video_path, publish_time) in enumerate(zip(video_paths, schedule), 1):
        # Convert UTC time back to local timezone for display
        local_time = publish_time.astimezone(config.timezone)
        
        print(f"Video {i:<4} {local_time.strftime('%Y-%m-%d'):<15} "
              f"{local_time.strftime('%I:%M %p'):<20} "
              f"{publish_time.strftime('%Y-%m-%d %H:%M %Z'):<20}")
    
    print("=" * 80)
    
    # Validate schedule
    print("\n=== Schedule Validation ===")
    if config.validate_schedule(schedule):
        print("✅ Schedule is valid")
        print("✅ Videos are properly distributed across days")
        print("✅ Minimum interval between uploads is maintained")
        print("✅ Maximum videos per week limit is respected")
    else:
        print("❌ Schedule validation failed")
    
    # Print day-wise distribution
    print("\n=== Day-wise Distribution ===")
    day_counts = {}
    for time in schedule:
        local_time = time.astimezone(config.timezone)
        day = local_time.strftime('%A')
        day_counts[day] = day_counts.get(day, 0) + 1
    
    for day, count in sorted(day_counts.items()):
        print(f"{day:<10}: {count} video(s)")

def main():
    # Simulate different scenarios
    
    # Scenario 1: 5 videos (less than a week)
    print("\n=== Scenario 1: 5 Videos ===")
    video_paths_1 = [f"video_{i}.mp4" for i in range(5)]
    simulate_video_upload(video_paths_1)
    
    # Scenario 2: 10 videos (more than a week)
    print("\n=== Scenario 2: 10 Videos ===")
    video_paths_2 = [f"video_{i}.mp4" for i in range(10)]
    simulate_video_upload(video_paths_2)
    
    # Scenario 3: 20 videos (multiple weeks)
    print("\n=== Scenario 3: 20 Videos ===")
    video_paths_3 = [f"video_{i}.mp4" for i in range(20)]
    simulate_video_upload(video_paths_3)

if __name__ == "__main__":
    main() 