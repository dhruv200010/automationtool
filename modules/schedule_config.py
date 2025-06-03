from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
import json
import os
import pytz
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import sys
import logging

logger = logging.getLogger(__name__)

def safe_encode(text: str) -> str:
    return text.encode(sys.stdout.encoding or 'utf-8', errors='ignore').decode()

def safe_log(logger_func, text):
    try:
        logger_func(text)
    except UnicodeEncodeError:
        logger_func(safe_encode(text))

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
        scheduled_videos = self.fetch_scheduled_videos()
        safe_log(logger.info, f"Fetched {len(scheduled_videos)} scheduled videos.")
        
        while videos_scheduled < num_videos:
            # Get next available time slot
            next_time = self.get_next_publish_time(current_time)
            
            # Skip if the day already has a scheduled video
            if any(scheduled_time.date() == next_time.date() for scheduled_time in scheduled_videos):
                safe_log(logger.info, f"Skipping day {next_time.date()} as it already has a scheduled video.")
                current_time = next_time + timedelta(days=1)
                continue
            
            # Ensure minimum interval between uploads
            if schedule:
                min_interval = timedelta(hours=self.min_interval_hours)
                time_since_last = next_time - schedule[-1]
                
                if time_since_last < min_interval:
                    # Calculate the next valid time that respects the minimum interval
                    next_time = schedule[-1] + min_interval
                    # If this pushes us to next day, get the next available time slot
                    if next_time.date() != schedule[-1].date():
                        next_time = self.get_next_publish_time(next_time)
            
            schedule.append(next_time)
            current_time = next_time + timedelta(hours=self.min_interval_hours)  # Move past minimum interval
            videos_scheduled += 1
        
        return schedule

    def fetch_scheduled_videos(self) -> List[datetime]:
        """
        Fetch the list of already scheduled videos from YouTube.
        
        Returns:
            List of scheduled publish times in UTC
        """
        if not self.credentials:
            safe_log(logger.info, "No credentials provided. Cannot fetch scheduled videos.")
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
                safe_log(logger.info, "No videos found in your channel.")
                return []

            # Step 2: Fetch details for these video IDs using videos().list
            video_response = youtube.videos().list(
                part="status,snippet",
                id=",".join(video_ids)
            ).execute()

            # Use a dictionary to store unique scheduled videos by video ID
            scheduled_videos_dict = {}
            safe_log(logger.info, "\n=== Scheduled Videos ===")
            safe_log(logger.info, "======================")
            
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
                        safe_log(logger.info, f"{title}")
                        safe_log(logger.info, f"   Video ID: {video_id}")
                        safe_log(logger.info, f"   Scheduled for: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                        safe_log(logger.info, "----------------------")

            scheduled_videos = [time for _, time in scheduled_videos_dict.values()]
            
            if not scheduled_videos:
                safe_log(logger.info, "No scheduled videos found.")
            else:
                safe_log(logger.info, f"\nTotal unique scheduled videos: {len(scheduled_videos)}")
            
            return scheduled_videos

        except Exception as e:
            safe_log(logger.error, f"Error fetching scheduled videos: {str(e)}")
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
            safe_log(logger.error, "Empty schedule provided")
            return False
            
        # Sort schedule to ensure chronological order
        schedule = sorted(schedule)
        now = datetime.now(pytz.UTC)
        
        # Filter out past times
        schedule = [s for s in schedule if s > now]
        if not schedule:
            safe_log(logger.error, "No future scheduled times found")
            return False
            
        # Debug logging for intervals
        safe_log(logger.info, "\n=== Schedule Intervals ===")
        for i in range(1, len(schedule)):
            interval = (schedule[i] - schedule[i-1]).total_seconds() / 3600
            safe_log(logger.info, f"Video {i}: {schedule[i-1]} → {schedule[i]} | Interval: {interval:.2f} hrs")
            
        # Check minimum interval between uploads
        for i in range(1, len(schedule)):
            time_diff = schedule[i] - schedule[i-1]
            hours_diff = time_diff.total_seconds() / 3600
            
            # Allow small negative intervals (up to 1 hour) due to timezone conversions
            if hours_diff < -1:
                safe_log(logger.error, f"Invalid interval between uploads: {hours_diff:.1f} hours")
                return False
            elif hours_diff < self.min_interval_hours:
                safe_log(logger.warning, f"Interval between uploads ({hours_diff:.1f} hours) is less than minimum ({self.min_interval_hours} hours)")
                # Don't fail validation for this, just warn
        
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
                safe_log(logger.error, f"Week starting {week} has {count} videos (max allowed: {self.max_videos_per_week})")
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