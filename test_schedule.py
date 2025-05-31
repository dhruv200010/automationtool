from modules.schedule_config import ScheduleConfig
from datetime import datetime, timedelta
import os
import pytz

def test_schedule():
    # Create schedule config
    config = ScheduleConfig()
    
    # Print current timezone and time
    print(f"\nCurrent Timezone: {config.timezone.zone}")
    print(f"Current Time: {config.get_current_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Print current schedule
    print("\nCurrent Schedule:")
    for day, time in config.daily_schedule.items():
        print(f"{day.capitalize()}: {time.strftime('%H:%M')} {config.timezone.zone}")
    
    # Test scheduling 5 videos
    print("\nScheduling 5 videos:")
    schedule = config.get_schedule_for_videos(5)
    
    for i, time in enumerate(schedule, 1):
        # Convert UTC time back to local timezone for display
        local_time = time.astimezone(config.timezone)
        print(f"Video {i}: {local_time.strftime('%Y-%m-%d %H:%M %Z')}")
    
    # Test schedule validation
    print("\nValidating schedule...")
    if config.validate_schedule(schedule):
        print("✅ Schedule is valid")
    else:
        print("❌ Schedule is invalid")
    
    # Test timezone change
    print("\nTesting timezone change to US/Pacific...")
    try:
        config.set_timezone('America/Los_Angeles')
        print(f"✅ Timezone changed to: {config.timezone.zone}")
        print(f"Current Time: {config.get_current_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    except ValueError as e:
        print(f"❌ Error changing timezone: {e}")
    
    # Test invalid timezone
    print("\nTesting invalid timezone...")
    try:
        config.set_timezone('Invalid/Timezone')
        print("❌ Should have raised an error")
    except ValueError as e:
        print(f"✅ Caught invalid timezone: {e}")
    
    # Test updating schedule
    print("\nUpdating Monday schedule to 09:00...")
    try:
        config.update_schedule('monday', '09:00')
        print("✅ Schedule updated successfully")
    except ValueError as e:
        print(f"❌ Error updating schedule: {e}")
    
    # Test invalid time format
    print("\nTesting invalid time format...")
    try:
        config.update_schedule('tuesday', '25:00')
        print("❌ Should have raised an error")
    except ValueError as e:
        print(f"✅ Caught invalid time format: {e}")
    
    # Test invalid day
    print("\nTesting invalid day...")
    try:
        config.update_schedule('invalid_day', '10:00')
        print("❌ Should have raised an error")
    except ValueError as e:
        print(f"✅ Caught invalid day: {e}")

if __name__ == "__main__":
    test_schedule() 