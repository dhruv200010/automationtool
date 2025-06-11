from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
import json
import os
import pytz
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import sys
import logging
from pathlib import Path
import pickle

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler if not already exists
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def safe_encode(text: str) -> str:
    return text.encode(sys.stdout.encoding or 'utf-8', errors='ignore').decode()

def safe_log(logger_func, text):
    try:
        logger_func(text)
    except UnicodeEncodeError:
        logger_func(safe_encode(text))

class ScheduleConfig:
    def __init__(self, config_file: str = 'config/master_config.json', credentials=None):
        self.config_file = config_file
        self.credentials = credentials
        self.timezone = pytz.timezone('Asia/Kolkata')
        self.daily_schedule = {}
        self.videos_per_day = 1
        self.min_interval_hours = 4
        self.max_videos_per_week = 7
        self._scheduled_videos_cache = None
        self._last_fetch_time = None
        self._cache_duration = timedelta(minutes=5)  # Cache for 5 minutes
        safe_log(logger.info, f"Initializing ScheduleConfig with timezone: {self.timezone.zone}")
        
        # If credentials are provided as a path, load them
        if isinstance(credentials, (str, Path)):
            try:
                with open(credentials, 'rb') as token:
                    self.credentials = pickle.load(token)
                safe_log(logger.info, "Loaded credentials from file")
            except Exception as e:
                safe_log(logger.error, f"Failed to load credentials from file: {str(e)}")
                self.credentials = None
        
        # Validate credentials if provided
        if self.credentials:
            try:
                # Test the credentials by making a simple API call
                youtube = build('youtube', 'v3', credentials=self.credentials)
                youtube.channels().list(part='snippet', mine=True).execute()
                safe_log(logger.info, "Successfully validated YouTube credentials")
            except Exception as e:
                safe_log(logger.error, f"Invalid YouTube credentials: {str(e)}")
                self.credentials = None
        else:
            safe_log(logger.warning, "No YouTube credentials provided. Scheduling will be based on local configuration only.")
        
        self.load_config()

    def load_config(self):
        """Load configuration from master_config.json or use defaults"""
        config_path = Path(__file__).parent.parent / self.config_file
        safe_log(logger.info, f"Loading configuration from: {config_path}")
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                master_config = json.load(f)
                config = master_config.get('schedule_config', {})
                
                self.daily_schedule = {
                    day: datetime.strptime(t, '%H:%M').time()
                    for day, t in config.get('daily_schedule', {}).items()
                }
                self.videos_per_day = config.get('videos_per_day', 1)
                self.min_interval_hours = config.get('min_interval_hours', 4)
                self.max_videos_per_week = config.get('max_videos_per_week', 7)
                
                if 'timezone' in config:
                    self.timezone = pytz.timezone(config['timezone'])
                
                safe_log(logger.info, "Loaded configuration:")
                safe_log(logger.info, f"- Videos per day: {self.videos_per_day}")
                safe_log(logger.info, f"- Min interval hours: {self.min_interval_hours}")
                safe_log(logger.info, f"- Max videos per week: {self.max_videos_per_week}")
                safe_log(logger.info, f"- Timezone: {self.timezone.zone}")
                safe_log(logger.info, "Daily schedule:")
                for day, time in self.daily_schedule.items():
                    safe_log(logger.info, f"  {day}: {time.strftime('%H:%M')}")
        else:
            safe_log(logger.warning, f"Config file not found at {config_path}, using defaults")
            # Default configuration
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
        """Save current configuration to master_config.json"""
        config_path = Path(__file__).parent.parent / self.config_file
        
        # Read existing master config if it exists
        master_config = {}
        if config_path.exists():
            with open(config_path, 'r') as f:
                master_config = json.load(f)
        
        # Update schedule_config section
        master_config['schedule_config'] = {
            'daily_schedule': {
                day: t.strftime('%H:%M')
                for day, t in self.daily_schedule.items()
            },
            'videos_per_day': self.videos_per_day,
            'min_interval_hours': self.min_interval_hours,
            'max_videos_per_week': self.max_videos_per_week,
            'timezone': self.timezone.zone
        }
        
        # Save updated master config
        with open(config_path, 'w') as f:
            json.dump(master_config, f, indent=4)

    def get_next_publish_time(self, current_time: datetime, day_offset: int = 0) -> datetime:
        """
        Calculate the next publish time based on the schedule.
        Strictly enforces one video per day and checks against already scheduled videos.
        
        Args:
            current_time: Current datetime
            day_offset: Number of days to offset from current day
            
        Returns:
            datetime: Next scheduled publish time in UTC
        """
        # Convert current time to local timezone
        local_time = current_time.astimezone(self.timezone)
        
        # Fetch already scheduled videos
        scheduled_videos = self.fetch_scheduled_videos()
        safe_log(logger.info, f"Found {len(scheduled_videos)} already scheduled videos")
        
        # Get the dates of already scheduled videos
        scheduled_dates = {video.astimezone(self.timezone).date() for video in scheduled_videos}
        
        # Try each day starting from the offset
        for offset in range(day_offset, day_offset + 14):  # Check up to 2 weeks ahead
            target_day = (local_time.weekday() + offset) % 7
            day_name = ['monday', 'tuesday', 'wednesday', 'thursday', 
                       'friday', 'saturday', 'sunday'][target_day]
            scheduled_time = self.daily_schedule[day_name]
            
            # Calculate the date for the target day
            target_date = local_time.date() + timedelta(days=offset)
            
            # Skip if this day already has a scheduled video
            if target_date in scheduled_dates:
                safe_log(logger.info, f"Skipping {target_date} as it already has a scheduled video")
                continue
            
            # Create the target datetime
            target_datetime = datetime.combine(target_date, scheduled_time)
            target_datetime = self.timezone.localize(target_datetime)
            
            # Only return if the time is in the future
            if target_datetime > local_time:
                safe_log(logger.info, f"Next available slot: {target_datetime.strftime('%Y-%m-%d %H:%M:%S')} {self.timezone.zone}")
                return target_datetime.astimezone(pytz.UTC)
        
        # If we get here, we couldn't find a slot in the next two weeks
        safe_log(logger.error, "Could not find an available slot in the next two weeks")
        return None

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
        
        safe_log(logger.info, f"\n=== Generating Schedule for {num_videos} Videos ===")
        safe_log(logger.info, f"Starting from: {start_time.astimezone(self.timezone).strftime('%Y-%m-%d %H:%M:%S')} {self.timezone.zone}")
        
        schedule = []
        current_time = start_time
        videos_scheduled = 0
        
        scheduled_videos = self.fetch_scheduled_videos()
        safe_log(logger.info, f"Found {len(scheduled_videos)} already scheduled videos")
        
        while videos_scheduled < num_videos:
            next_time = self.get_next_publish_time(current_time)
            if not next_time:
                safe_log(logger.error, "Could not find next available time slot")
                break
                
            local_time = next_time.astimezone(self.timezone)
            safe_log(logger.info, f"\nScheduling video {videos_scheduled + 1}:")
            safe_log(logger.info, f"Date: {local_time.strftime('%Y-%m-%d')}")
            safe_log(logger.info, f"Time: {local_time.strftime('%H:%M:%S')} {self.timezone.zone}")
            safe_log(logger.info, f"UTC: {next_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            schedule.append(next_time)
            current_time = next_time + timedelta(hours=self.min_interval_hours)
            videos_scheduled += 1
        
        if schedule:
            safe_log(logger.info, "\n=== Final Schedule ===")
            safe_log(logger.info, "====================")
            for i, time in enumerate(schedule, 1):
                local_time = time.astimezone(self.timezone)
                safe_log(logger.info, f"Video {i}: {local_time.strftime('%Y-%m-%d %H:%M:%S')} {self.timezone.zone}")
        
        return schedule

    def fetch_scheduled_videos(self, verbose=True) -> List[datetime]:
        """
        Fetch the list of already scheduled videos from YouTube.
        
        Args:
            verbose (bool): Whether to show detailed logging of scheduled videos
            
        Returns:
            List of scheduled publish times in UTC
        """
        # Check if we have a valid cache
        now = datetime.now(pytz.UTC)
        if (self._scheduled_videos_cache is not None and 
            self._last_fetch_time is not None and 
            now - self._last_fetch_time < self._cache_duration):
            if verbose:
                safe_log(logger.info, f"Using cached scheduled videos (last fetched {self._last_fetch_time.strftime('%Y-%m-%d %H:%M:%S')} UTC)")
            return self._scheduled_videos_cache

        if not self.credentials:
            safe_log(logger.warning, "No credentials provided. Cannot fetch scheduled videos.")
            return []

        try:
            safe_log(logger.info, "Fetching scheduled videos from YouTube...")
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

            safe_log(logger.info, f"Found {len(video_ids)} videos in channel")

            # Step 2: Fetch details for these video IDs using videos().list
            video_response = youtube.videos().list(
                part="status,snippet",
                id=",".join(video_ids)
            ).execute()

            scheduled_videos_dict = {}
            if verbose:
                safe_log(logger.info, "\n=== Currently Scheduled Videos ===")
                safe_log(logger.info, "=================================")
            
            for item in video_response.get("items", []):
                video_id = item['id']
                status = item.get("status", {})
                privacy_status = status.get("privacyStatus", "")
                publish_at = status.get("publishAt")
                
                if privacy_status == "private" and publish_at:
                    title = item['snippet']['title']
                    scheduled_time = datetime.fromisoformat(publish_at.replace('Z', '+00:00'))
                    local_time = scheduled_time.astimezone(self.timezone)
                    
                    if video_id not in scheduled_videos_dict:
                        scheduled_videos_dict[video_id] = (title, scheduled_time)
                        if verbose:
                            safe_log(logger.info, f"\nTitle: {title}")
                            safe_log(logger.info, f"Video ID: {video_id}")
                            safe_log(logger.info, f"Scheduled for: {local_time.strftime('%Y-%m-%d %H:%M:%S')} {self.timezone.zone}")
                            safe_log(logger.info, f"UTC Time: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                            safe_log(logger.info, "----------------------------------------")

            scheduled_videos = [time for _, time in scheduled_videos_dict.values()]
            
            if not scheduled_videos:
                safe_log(logger.info, "No scheduled videos found.")
            else:
                if verbose:
                    safe_log(logger.info, f"\nTotal unique scheduled videos: {len(scheduled_videos)}")
                    safe_log(logger.info, "Scheduled dates:")
                    for video_time in sorted(scheduled_videos):
                        local_time = video_time.astimezone(self.timezone)
                        safe_log(logger.info, f"- {local_time.strftime('%Y-%m-%d %H:%M:%S')} {self.timezone.zone}")
                else:
                    safe_log(logger.info, f"Found {len(scheduled_videos)} scheduled videos")
            
            # Update cache
            self._scheduled_videos_cache = scheduled_videos
            self._last_fetch_time = now
            
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

    def clear_scheduled_videos_cache(self):
        """Clear the scheduled videos cache to force a fresh fetch"""
        self._scheduled_videos_cache = None
        self._last_fetch_time = None 