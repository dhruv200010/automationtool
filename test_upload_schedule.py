import os
import json
from modules.schedule_config import ScheduleConfig
from modules.upload_youtube import upload_to_youtube
from datetime import datetime, timedelta
import pytz
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import sys
import re
from pathlib import Path

# Add the parent directory to sys.path to import youtube_config.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from youtube_config import YOUTUBE_API_SCOPES

# Define the scopes
SCOPES = YOUTUBE_API_SCOPES

def get_authenticated_service():
    credentials = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            credentials = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secrets.json', SCOPES)
            credentials = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(credentials, token)

    return credentials

def load_titles():
    """Load titles from shorts_titles.json"""
    try:
        with open(Path("output") / "shorts_titles.json", 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: shorts_titles.json not found!")
        return {}
    except json.JSONDecodeError:
        print("Error: Invalid JSON in shorts_titles.json!")
        return {}

def normalize_path(path):
    """Normalize path to use forward slashes"""
    return path.replace('\\', '/')

def get_schedule_for_videos_with_limit(config, video_files, max_videos_per_week=7):
    """Generate a schedule that respects the max_videos_per_week limit and minimum intervals"""
    schedule = []
    current_time = datetime.now(pytz.UTC)
    videos_scheduled = 0
    week_start = current_time
    
    # Fetch already scheduled videos
    scheduled_videos = config.fetch_scheduled_videos()
    
    for video_path in video_files:
        # If we've scheduled max videos for this week, move to next week
        if videos_scheduled >= max_videos_per_week:
            week_start = week_start + timedelta(days=7)
            videos_scheduled = 0
            current_time = week_start
        
        # Get next available time slot
        next_time = config.get_next_publish_time(current_time)
        
        # Skip if the day already has a scheduled video
        while any(scheduled_time.date() == next_time.date() for scheduled_time in scheduled_videos):
            next_time = next_time + timedelta(days=1)
        
        # Ensure minimum interval between uploads
        if schedule and (next_time - schedule[-1]).total_seconds() < config.min_interval_hours * 3600:
            next_time = schedule[-1] + timedelta(hours=config.min_interval_hours)
            # If this pushes us to next day, get the next available time slot
            if next_time.date() != schedule[-1].date():
                next_time = config.get_next_publish_time(next_time)
        
        schedule.append(next_time)
        current_time = next_time + timedelta(hours=config.min_interval_hours)  # Move past minimum interval
        videos_scheduled += 1
    
    return schedule

def main():
    # Get authenticated credentials
    credentials = get_authenticated_service()
    
    # Create an instance of ScheduleConfig with the credentials
    config = ScheduleConfig(credentials=credentials)
    
    # Load titles from shorts_titles.json
    shorts_titles = load_titles()
    
    # Get the list of videos from the shorts directory
    shorts_dir = 'output/shorts'
    video_files = [os.path.join(shorts_dir, f) for f in os.listdir(shorts_dir) if f.endswith('.mp4')]
    
    # Normalize paths in shorts_titles
    normalized_shorts_titles = {normalize_path(k): v for k, v in shorts_titles.items()}
    
    # Filter videos that have titles in shorts_titles.json
    video_files = [v for v in video_files if normalize_path(v) in normalized_shorts_titles]
    
    if not video_files:
        print("No videos found in shorts directory or no matching titles in shorts_titles.json!")
        print("\nAvailable videos in shorts directory:")
        for vf in [os.path.join(shorts_dir, f) for f in os.listdir(shorts_dir) if f.endswith('.mp4')]:
            print(f"- {vf}")
        print("\nTitles in shorts_titles.json:")
        for path, data in shorts_titles.items():
            print(f"- {path}: {data['title']} {' '.join(data['hashtags'])}")
        return
    
    # Get schedule that respects max_videos_per_week limit
    schedule = get_schedule_for_videos_with_limit(config, video_files, config.max_videos_per_week)
    
    print("\n=== Upload Schedule Test ===")
    print(f"Number of videos to schedule: {len(video_files)}")
    print(f"Current timezone: {config.timezone.zone}")
    print(f"Current time: {config.get_current_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    print("\n=== Schedule Details ===")
    print("=" * 100)
    print(f"{'Video':<20} {'Title':<30} {'Scheduled Date':<15} {'Scheduled Time (IST)':<20} {'UTC Time':<20}")
    print("-" * 100)

    for video_path, publish_time in zip(video_files, schedule):
        # Ensure publish_time is within YouTube's allowed range
        now_utc = datetime.now(pytz.UTC)
        min_future_time = now_utc + timedelta(minutes=15)
        max_future_time = now_utc + timedelta(days=180)
        
        if publish_time < min_future_time:
            print(f"❌ Scheduled time for {os.path.basename(video_path)} is too soon. Skipping upload.")
            continue
        if publish_time > max_future_time:
            print(f"❌ Scheduled time for {os.path.basename(video_path)} is too far in the future. Skipping upload.")
            continue

        # Format publish_time as ISO 8601 without microseconds and with 'Z'
        publish_time_str = publish_time.replace(microsecond=0).isoformat().replace('+00:00', 'Z')

        title_data = normalized_shorts_titles[normalize_path(video_path)]
        
        # Clean up title
        title = title_data['title'].strip('"')  # Remove quotes
        title = re.sub(r'^Title:\s*', '', title, flags=re.IGNORECASE)  # Remove "Title:" prefix
        title = re.sub(r'\{(\w+)\}', r'\1', title)  # Remove curly braces from title
        
        # Clean up hashtags
        hashtags = [tag.strip() for tag in title_data['hashtags']]  # Remove any extra spaces
        hashtags = [re.sub(r'[{}]', '', tag) for tag in hashtags]  # Remove curly braces
        hashtags = [tag if tag.startswith('#') else f"#{tag}" for tag in hashtags]  # Ensure all tags start with #
        
        # Get description
        description = title_data.get('description', '')
        if not description:
            # Fallback to title and hashtags if no description
            description = f"{title}\n\n{' '.join(hashtags)}"
        
        # Use hashtags as tags for the video
        tags = hashtags + ["shorts", "youtube shorts", "short video"]
        
        video_id = upload_to_youtube(video_path, title, description, tags, publish_time=publish_time_str)
        if video_id:
            print(f"✅ Uploaded {title} (Video ID: {video_id})")
        else:
            print(f"❌ Failed to upload {title}")

if __name__ == "__main__":
    main() 