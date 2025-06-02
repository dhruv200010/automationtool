from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
import json
import os
import pytz
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class ScheduleConfig:
    def __init__(self, config_file: str = 'schedule_config.json', credentials=None):
        self.config_file = config_file
        self.credentials = credentials  # Store the credentials
        # Default to India timezone
        self.timezone = pytz.timezone('Asia/Kolkata')
        self.load_config()

    def load_config(self):
        """Load configuration from JSON file or use defaults"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                self.daily_schedule = {
                    day: datetime.strptime(t, '%H:%M').time()
                    for day, t in config['daily_schedule'].items()
                }
                self.videos_per_day = config['videos_per_day']
                self.min_interval_hours = config['min_interval_hours']
                self.max_videos_per_week = config['max_videos_per_week']
                # Load timezone if specified, otherwise use default
                if 'timezone' in config:
                    self.timezone = pytz.timezone(config['timezone'])
        else:
            # Default configuration with new schedule
            self.daily_schedule = {
                'monday': time(20, 0),    # 8:00 PM IST
                'tuesday': time(20, 0),   # 8:00 PM IST
                'wednesday': time(20, 0), # 8:00 PM IST
                'thursday': time(20, 0),  # 8:00 PM IST
                'friday': time(20, 0),    # 8:00 PM IST
                'saturday': time(11, 0),  # 11:00 AM IST
                'sunday': time(11, 0)     # 11:00 AM IST
            }
            self.videos_per_day = 1
            self.min_interval_hours = 4
            self.max_videos_per_week = 7
            self.save_config()

    def save_config(self):
        """Save current configuration to JSON file"""
        config = {
            'daily_schedule': {
                day: t.strftime('%H:%M')
                for day, t in self.daily_schedule.items()
            },
            'videos_per_day': self.videos_per_day,
            'min_interval_hours': self.min_interval_hours,
            'max_videos_per_week': self.max_videos_per_week,
            'timezone': self.timezone.zone
        }
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)

    def get_next_publish_time(self, current_time: datetime, day_offset: int = 0) -> datetime:
        """
        Calculate the next publish time based on the schedule.
        
        Args:
            current_time: Current datetime
            day_offset: Number of days to offset from current day
            
        Returns:
            datetime: Next scheduled publish time in UTC
        """
        # Convert current time to local timezone
        local_time = current_time.astimezone(self.timezone)
        
        for offset in range(day_offset, day_offset + 8):  # Check up to 7 days ahead
            target_day = (local_time.weekday() + offset) % 7
            day_name = ['monday', 'tuesday', 'wednesday', 'thursday', 
                       'friday', 'saturday', 'sunday'][target_day]
            scheduled_time = self.daily_schedule[day_name]
            # Calculate the date for the target day
            target_date = local_time.date() + timedelta(days=offset)
            target_datetime = datetime.combine(target_date, scheduled_time)
            target_datetime = self.timezone.localize(target_datetime)
            if target_datetime > local_time:
                return target_datetime.astimezone(pytz.UTC)
        # Fallback: return the next week's first scheduled time
        # (should never hit this unless all times are in the past)
        target_day = (local_time.weekday() + day_offset) % 7
        day_name = ['monday', 'tuesday', 'wednesday', 'thursday', 
                   'friday', 'saturday', 'sunday'][target_day]
        scheduled_time = self.daily_schedule[day_name]
        target_date = local_time.date() + timedelta(days=day_offset + 7)
        target_datetime = datetime.combine(target_date, scheduled_time)
        target_datetime = self.timezone.localize(target_datetime)
        return target_datetime.astimezone(pytz.UTC)

    def get_schedule_for_videos(self, num_videos: int, start_time: Optional[datetime] = None) -> List[datetime]:
        """
        Generate a schedule for multiple videos on consecutive days, skipping days that already have scheduled videos.
        
        Args:
            num_videos: Number of videos to schedule
            start_time: Optional start time (defaults to current time)
            
        Returns:
            List of scheduled publish times in UTC
        """
        if start_time is None:
            start_time = datetime.now(pytz.UTC)
        
        schedule = []
        current_time = start_time
        videos_scheduled = 0
        
        # Fetch the list of already scheduled videos
        scheduled_videos = self.fetch_scheduled_videos()  # Implement this method to fetch scheduled videos
        print(f"Fetched {len(scheduled_videos)} scheduled videos.")
        
        while videos_scheduled < num_videos:
            next_time = self.get_next_publish_time(current_time)
            if next_time <= current_time + timedelta(minutes=15) or next_time > current_time + timedelta(days=180):
                raise ValueError(f"Invalid scheduled time for video {videos_scheduled + 1}: {next_time}")
            # Check if the day already has a scheduled video
            if any(scheduled_time.date() == next_time.date() for scheduled_time in scheduled_videos):
                print(f"Skipping day {next_time.date()} as it already has a scheduled video.")
                current_time = next_time + timedelta(days=1)
                continue
            schedule.append(next_time)
            current_time = next_time + timedelta(seconds=1)  # move just past last scheduled time
            videos_scheduled += 1
        
        return schedule

    def fetch_scheduled_videos(self) -> List[datetime]:
        """
        Fetch the list of already scheduled videos from YouTube.
        
        Returns:
            List of scheduled publish times in UTC
        """
        if not self.credentials:
            print("No credentials provided. Cannot fetch scheduled videos.")
            return []

        try:
            # Set up the YouTube API client
            youtube = build('youtube', 'v3', credentials=self.credentials)

            # Step 1: Get your video IDs using search().list
            search_response = youtube.search().list(
                part="id",
                forMine=True,
                type="video",
                maxResults=50
            ).execute()

            video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
            if not video_ids:
                print("No videos found in your channel.")
                return []

            # Step 2: Fetch details for these video IDs using videos().list
            video_response = youtube.videos().list(
                part="status,snippet",
                id=",".join(video_ids)
            ).execute()

            # Use a dictionary to store unique scheduled videos by video ID
            scheduled_videos_dict = {}
            print("\n=== Scheduled Videos ===")
            print("======================")
            
            for item in video_response.get("items", []):
                video_id = item['id']
                status = item.get("status", {})
                privacy_status = status.get("privacyStatus", "")
                publish_at = status.get("publishAt")
                
                if privacy_status == "private" and publish_at:
                    title = item['snippet']['title']
                    scheduled_time = datetime.fromisoformat(publish_at.replace('Z', '+00:00'))
                    # Only add if we haven't seen this video ID before
                    if video_id not in scheduled_videos_dict:
                        scheduled_videos_dict[video_id] = (title, scheduled_time)
                        print(f"📅 {title}")
                        print(f"   Video ID: {video_id}")
                        print(f"   Scheduled for: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                        print("----------------------")

            scheduled_videos = [time for _, time in scheduled_videos_dict.values()]
            
            if not scheduled_videos:
                print("No scheduled videos found.")
            else:
                print(f"\nTotal unique scheduled videos: {len(scheduled_videos)}")
            
            return scheduled_videos

        except Exception as e:
            print(f"Error fetching scheduled videos: {str(e)}")
            return []

    def validate_schedule(self, schedule: List[datetime]) -> bool:
        """
        Validate if a schedule meets the requirements.
        
        Args:
            schedule: List of scheduled times
            
        Returns:
            bool: True if schedule is valid
        """
        if not schedule:
            return False
            
        # Check minimum interval between uploads
        for i in range(len(schedule) - 1):
            time_diff = schedule[i + 1] - schedule[i]
            if time_diff.total_seconds() < self.min_interval_hours * 3600:
                print(f"❌ Minimum interval between uploads not met: {time_diff.total_seconds() / 3600:.1f} hours")
                return False
        
        # Check maximum videos per week
        # Group videos by week
        videos_by_week = {}
        for time in schedule:
            # Get the start of the week (Monday) for this time
            local_time = time.astimezone(self.timezone)
            week_start = local_time - timedelta(days=local_time.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            videos_by_week[week_key] = videos_by_week.get(week_key, 0) + 1
        
        # Check if any week has too many videos
        for week, count in videos_by_week.items():
            if count > self.max_videos_per_week:
                print(f"❌ Week starting {week} has {count} videos (max allowed: {self.max_videos_per_week})")
                return False
            
        return True

    def update_schedule(self, day: str, time_str: str):
        """
        Update schedule for a specific day.
        
        Args:
            day: Day of the week (monday, tuesday, etc.)
            time_str: Time in HH:MM format
        """
        if day.lower() not in self.daily_schedule:
            raise ValueError(f"Invalid day: {day}")
        
        try:
            new_time = datetime.strptime(time_str, '%H:%M').time()
            self.daily_schedule[day.lower()] = new_time
            self.save_config()
        except ValueError:
            raise ValueError(f"Invalid time format: {time_str}. Use HH:MM format.")

    def set_timezone(self, timezone_str: str):
        """
        Update the timezone setting.
        
        Args:
            timezone_str: Timezone string (e.g., 'Asia/Kolkata', 'America/New_York')
        """
        try:
            self.timezone = pytz.timezone(timezone_str)
            self.save_config()
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Invalid timezone: {timezone_str}")

    def get_current_time(self) -> datetime:
        """Get current time in the configured timezone"""
        return datetime.now(self.timezone)

    def set_videos_per_day(self, count: int):
        """Update videos per day setting"""
        if count < 1:
            raise ValueError("Videos per day must be at least 1")
        self.videos_per_day = count
        self.save_config()

    def set_min_interval(self, hours: int):
        """Update minimum interval between uploads"""
        if hours < 1:
            raise ValueError("Minimum interval must be at least 1 hour")
        self.min_interval_hours = hours
        self.save_config()

    def set_max_videos_per_week(self, count: int):
        """Update maximum videos per week"""
        if count < 1:
            raise ValueError("Maximum videos per week must be at least 1")
        self.max_videos_per_week = count
        self.save_config() 