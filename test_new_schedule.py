from modules.schedule_config import ScheduleConfig
from datetime import datetime, timedelta
import pytz

def test_new_schedule():
    # Create schedule config
    config = ScheduleConfig()
    
    # Print current timezone and time
    print(f"\nCurrent Timezone: {config.timezone.zone}")
    print(f"Current Time: {config.get_current_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Print the new schedule
    print("\nNew Schedule:")
    print("=" * 40)
    print("Day\t\tTime (IST)")
    print("-" * 40)
    for day, time in config.daily_schedule.items():
        print(f"{day.capitalize()}\t\t{time.strftime('%I:%M %p')}")
    print("=" * 40)
    
    # Test scheduling 7 videos (one for each day)
    print("\nScheduling 7 videos (one for each day):")
    print("=" * 60)
    print("Video\tScheduled Time (IST)\t\tUTC Time")
    print("-" * 60)
    
    schedule = config.get_schedule_for_videos(7)
    for i, time in enumerate(schedule, 1):
        # Convert UTC time back to local timezone for display
        local_time = time.astimezone(config.timezone)
        print(f"Video {i}\t{local_time.strftime('%Y-%m-%d %I:%M %p %Z')}\t{time.strftime('%Y-%m-%d %H:%M %Z')}")
    print("=" * 60)
    
    # Validate the schedule
    print("\nValidating schedule...")
    if config.validate_schedule(schedule):
        print("✅ Schedule is valid")
        print("✅ All videos are scheduled at the correct times")
        print("✅ Minimum interval between uploads is maintained")
        print("✅ Maximum videos per week limit is respected")
    else:
        print("❌ Schedule validation failed")

if __name__ == "__main__":
    test_new_schedule() 