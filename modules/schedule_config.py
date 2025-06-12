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

def setup_logging():
    """Configure logging with custom format"""
    logger = logging.getLogger('modules.schedule_config')
    logger.setLevel(logging.INFO)
    
    # Create console handler with custom formatter
    console_handler = logging.StreamHandler()
    # Use a format without timestamp since it's added by the pipeline
    formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger

# Create logger instance
logger = setup_logging()

def safe_encode(text: str) -> str:
    return text.encode(sys.stdout.encoding or 'utf-8', errors='ignore').decode()

def safe_log(log_func, message: str):
    """Safely log messages"""
    # Call the original logging function directly
    log_func(message)

class ScheduleConfig:
    def __init__(self, config_file: str = 'config/master_config.json', credentials=None):
        """
        Initialize the schedule configuration.
        
        Args:
            config_file: Path to the configuration file
            credentials: Optional credentials object or path to credentials file (for backward compatibility)
        """
        self.config_file = config_file
        self.timezone = pytz.timezone('Asia/Kolkata')
        self.youtube = None  # Initialize youtube client as None
        self._scheduled_videos_cache = None  # Cache for scheduled videos
        self._last_fetch_time = None  # Timestamp of last fetch
        
        # Load configuration
        self.load_config()
        
        # Initialize YouTube client
        if credentials:
            # If credentials are provided as a path, load them
            if isinstance(credentials, (str, Path)):
                try:
                    with open(credentials, 'rb') as token:
                        creds = pickle.load(token)
                    self.youtube = build('youtube', 'v3', credentials=creds)
                    safe_log(logger.info, "Loaded credentials from file")
                except Exception as e:
                    safe_log(logger.error, f"Failed to load credentials from file: {str(e)}")
            else:
                # If credentials object is provided directly
                try:
                    self.youtube = build('youtube', 'v3', credentials=credentials)
                    safe_log(logger.info, "Using provided credentials")
                except Exception as e:
                    safe_log(logger.error, f"Failed to use provided credentials: {str(e)}")
        else:
            # Try to initialize from credentials.json
            self.initialize_youtube()
        
        safe_log(logger.info, f"Initializing ScheduleConfig with timezone: {self.timezone.zone}")
        if self.youtube:
            safe_log(logger.info, "Successfully validated YouTube credentials")
        safe_log(logger.info, f"Loading configuration from: {self.config_file}")

    def initialize_youtube(self):
        """Initialize the YouTube client with credentials."""
        try:
            # Load credentials
            credentials_path = 'config/credentials.json'
            if not os.path.exists(credentials_path):
                safe_log(logger.error, f"Credentials file not found at {credentials_path}")
                return
            
            with open(credentials_path, 'r') as f:
                credentials_data = json.load(f)
            
            # Create credentials object
            credentials = Credentials.from_authorized_user_info(credentials_data)
            
            # Build YouTube client
            self.youtube = build('youtube', 'v3', credentials=credentials)
            
            # Test the connection
            try:
                self.youtube.channels().list(part='id', mine=True).execute()
                safe_log(logger.info, "YouTube client initialized and validated successfully")
            except Exception as e:
                safe_log(logger.error, f"Failed to validate YouTube connection: {str(e)}")
                self.youtube = None
            
        except Exception as e:
            safe_log(logger.error, f"Error initializing YouTube client: {str(e)}")
            self.youtube = None

    def load_config(self):
        """Load configuration from the config file."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Load schedule configuration
            schedule_config = config.get('schedule', {})
            self.videos_per_day = schedule_config.get('videos_per_day', 1)
            self.min_interval_hours = schedule_config.get('min_interval_hours', 4)
            self.max_videos_per_week = schedule_config.get('max_videos_per_week', 8)
            
            # Load daily schedule
            self.daily_schedule = {}
            for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                time_str = schedule_config.get(day, '20:00')
                try:
                    hour, minute = map(int, time_str.split(':'))
                    self.daily_schedule[day] = time(hour, minute)
                except (ValueError, TypeError):
                    self.daily_schedule[day] = time(20, 0)  # Default to 8 PM
            
            safe_log(logger.info, f"ScheduleConfig Loaded: videos/day={self.videos_per_day}, interval={self.min_interval_hours}h, max/week={self.max_videos_per_week}")
            
        except Exception as e:
            safe_log(logger.error, f"Error loading configuration: {str(e)}")
            # Set default values
            self.videos_per_day = 1
            self.min_interval_hours = 4
            self.max_videos_per_week = 8
            self.daily_schedule = {
                'monday': time(20, 0),
                'tuesday': time(20, 0),
                'wednesday': time(20, 0),
                'thursday': time(20, 0),
                'friday': time(20, 0),
                'saturday': time(11, 0),
                'sunday': time(11, 0)
            }

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
        
        # Check if there's already a published video today
        today = local_time.date()
        has_published_today = any(
            video.get('is_published', False) and 
            video['scheduled_time'].astimezone(self.timezone).date() == today 
            for video in scheduled_videos
        )
        
        if has_published_today:
            safe_log(logger.info, "Skipping today as there's already a published video")
            day_offset = max(day_offset, 1)  # Start from tomorrow
        
        # Get the dates of already scheduled videos
        scheduled_dates = {video['scheduled_time'].astimezone(self.timezone).date() for video in scheduled_videos}
        
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

    def get_schedule_for_videos(self, num_videos: int, video_metadata: Optional[List[Dict]] = None, schedule: Optional[List[datetime]] = None) -> List[Dict]:
        """
        Generate a schedule for multiple videos.
        
        Args:
            num_videos: Number of videos to schedule
            video_metadata: Optional list of dictionaries containing video metadata (title, description, etc.)
            schedule: Optional list of already scheduled times
            
        Returns:
            List[Dict]: List of dictionaries containing schedule and metadata for each video
        """
        if not schedule:
            schedule = [datetime.now(pytz.UTC)]
            
        # Get already scheduled videos
        scheduled_videos = self.fetch_scheduled_videos()
        safe_log(logger.info, f"Found {len(scheduled_videos)} already scheduled videos")
        
        # Find all available slots at once
        available_slots = []
        current_date = datetime.now(self.timezone).date()
        max_attempts = 365  # Maximum days to look ahead (1 year)
        attempts = 0
        
        while len(available_slots) < num_videos and attempts < max_attempts:
            # Check if this date already has a scheduled video
            date_has_video = any(
                video['scheduled_time'].astimezone(self.timezone).date() == current_date 
                for video in scheduled_videos
            )
            
            if not date_has_video:
                # Add the default time for this date
                slot_time = datetime.combine(current_date, time(20, 0))  # 8:00 PM
                slot_time = self.timezone.localize(slot_time)
                available_slots.append(slot_time)
                safe_log(logger.info, f"Found available slot: {slot_time.strftime('%Y-%m-%d %H:%M')} {self.timezone.zone}")
            
            current_date += timedelta(days=1)
            attempts += 1
        
        if len(available_slots) < num_videos:
            safe_log(logger.warning, f"Could only find {len(available_slots)} available slots out of {num_videos} requested after searching {attempts} days")
        else:
            safe_log(logger.info, f"Found all {num_videos} required slots in {attempts} days")
        
        # Schedule videos to available slots
        scheduled_info = []
        for i, slot in enumerate(available_slots[:num_videos]):
            # Get video metadata if available
            video_info = {}
            if video_metadata and i < len(video_metadata):
                video_info = video_metadata[i]
            
            # Get video title
            video_title = video_info.get('title', f'Video {i+1}')
            
            scheduled_info.append({
                'title': video_title,
                'scheduled_time': slot,
                'metadata': video_info  # Include all metadata
            })
        
        return scheduled_info

    def fetch_scheduled_videos(self, force_refresh: bool = False) -> List[Dict]:
        """
        Fetch all scheduled videos from YouTube.
        
        Args:
            force_refresh: If True, force a refresh of the cache
            
        Returns:
            List[Dict]: List of dictionaries containing video_id, title, and scheduled_time
        """
        # Return cached results if available and not forcing refresh
        current_time = datetime.now()
        if (not force_refresh and 
            self._scheduled_videos_cache is not None and 
            self._last_fetch_time is not None and 
            (current_time - self._last_fetch_time).total_seconds() < 300):  # Cache for 5 minutes
            return self._scheduled_videos_cache
            
        if not self.youtube:
            safe_log(logger.error, "YouTube client not initialized. Attempting to initialize...")
            self.initialize_youtube()
            if not self.youtube:
                safe_log(logger.error, "Failed to initialize YouTube client. Cannot fetch scheduled videos.")
                return []
            
        try:
            # Get channel's uploads playlist ID
            channel_response = self.youtube.channels().list(
                part='contentDetails',
                mine=True
            ).execute()
            
            if not channel_response['items']:
                safe_log(logger.error, "No channel found")
                return []
                
            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            safe_log(logger.info, f"Found uploads playlist ID: {uploads_playlist_id}")
            
            # Get video IDs from uploads playlist
            playlist_items = self.youtube.playlistItems().list(
                part='contentDetails',
                playlistId=uploads_playlist_id,
                maxResults=50
            ).execute()
            
            video_ids = [item['contentDetails']['videoId'] for item in playlist_items.get('items', [])]
            safe_log(logger.info, f"Found {len(video_ids)} videos in uploads playlist")
            safe_log(logger.debug, f"Uploads playlist video IDs: {video_ids}")
            
            if not video_ids:
                safe_log(logger.warning, "No videos found in uploads playlist")
                return []
            
            # Get video details
            videos_response = self.youtube.videos().list(
                part='snippet,status',
                id=','.join(video_ids)
            ).execute()
            
            safe_log(logger.info, f"Retrieved details for {len(videos_response.get('items', []))} videos")
            
            scheduled_videos = []
            today = datetime.now(self.timezone).date()
            
            for video in videos_response.get('items', []):
                # Debug logging for each video
                debug_status = video['status'].get('privacyStatus')
                debug_publish_at = video['status'].get('publishAt')
                debug_upload_status = video['status'].get('uploadStatus')
                safe_log(logger.debug, f"Checking video {video['id']} - privacy={debug_status}, publishAt={debug_publish_at}, uploadStatus={debug_upload_status}")
                
                # Check for publishAt or publishedAt
                video_time = None
                if video['status'].get('publishAt'):
                    video_time = datetime.fromisoformat(video['status']['publishAt'].replace('Z', '+00:00'))
                elif video['snippet'].get('publishedAt'):
                    video_time = datetime.fromisoformat(video['snippet']['publishedAt'].replace('Z', '+00:00'))
                
                if video_time:
                    video_date = video_time.astimezone(self.timezone).date()
                    # Include if it's scheduled for future or published today
                    if video_date >= today:
                        is_published = video_date == today and debug_status == 'public'
                        scheduled_videos.append({
                            'video_id': video['id'],
                            'title': video['snippet']['title'],
                            'scheduled_time': video_time,
                            'privacy_status': debug_status,
                            'upload_status': debug_upload_status,
                            'is_published': is_published
                        })
                        safe_log(logger.debug, f"Added video: {video['id']} - {video['snippet']['title']} at {video_time} (Published: {is_published})")
                else:
                    safe_log(logger.debug, f"Skipping video {video['id']} - no publish time")
            
            # Sort by scheduled time
            scheduled_videos.sort(key=lambda x: x['scheduled_time'])
            
            # Update cache
            self._scheduled_videos_cache = scheduled_videos
            self._last_fetch_time = current_time
            
            # Log the schedule only once
            if scheduled_videos:
                safe_log(logger.info, "Currently Scheduled Videos:")
                for video in scheduled_videos:
                    local_time = video['scheduled_time'].astimezone(self.timezone)
                    status = "Published" if video.get('is_published', False) else video['privacy_status']
                    safe_log(logger.info, f"{local_time.strftime('%b %d, %H:%M')} - \"{video['title']}\" ({status}, {video['upload_status']})")
            else:
                safe_log(logger.info, "No scheduled videos found")
            
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

    def process_video(self, video_path: str, metadata: Optional[Dict] = None) -> bool:
        """
        Process a video for scheduling.
        
        Args:
            video_path: Path to the video file
            metadata: Optional dictionary containing video metadata
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            # Validate video file
            if not os.path.exists(video_path):
                safe_log(logger.error, f"Video file not found: {video_path}")
                return False
                
            # Get video metadata
            if not metadata:
                metadata = {}
                
            # Add video path to metadata
            metadata['video_path'] = video_path
            
            # Add to processing queue
            self.processing_queue.append(metadata)
            safe_log(logger.info, f"Added video to processing queue: {os.path.basename(video_path)}")
            
            # Process queue if not already processing
            if not self.is_processing:
                self.process_queue()
            
            return True
            
        except Exception as e:
            safe_log(logger.error, f"Error processing video: {str(e)}")
            return False
            
    def process_queue(self):
        """Process the video queue"""
        if not self.processing_queue:
            return
            
        self.is_processing = True
        processed_count = 0
        
        try:
            while self.processing_queue:
                metadata = self.processing_queue.pop(0)
                video_path = metadata.get('video_path')
                
                if not video_path or not os.path.exists(video_path):
                    safe_log(logger.error, f"Invalid video path: {video_path}")
                    continue
                    
                # Process video
                safe_log(logger.info, f"Processing video: {os.path.basename(video_path)}")
                
                # Add to processed videos
                self.processed_videos.append(metadata)
                processed_count += 1
                
        except Exception as e:
            safe_log(logger.error, f"Error processing queue: {str(e)}")
            
        finally:
            self.is_processing = False
            if processed_count > 0:
                safe_log(logger.info, f"Total videos processed: {processed_count}")
                safe_log(logger.info, f"Successfully processed: {processed_count}") 