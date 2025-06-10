import os
import json
import sys
import re
import pickle
from datetime import datetime, timedelta
from pathlib import Path
import pytz
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import logging

# Add the project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from modules.upload_youtube import upload_to_youtube
from modules.schedule_config import ScheduleConfig
from config.youtube_config import YOUTUBE_API_SCOPES, TOKEN_FILE, CLIENT_SECRETS_FILE

logger = logging.getLogger(__name__)

# Define the scopes
SCOPES = YOUTUBE_API_SCOPES

def get_authenticated_service():
    credentials = None
    # The file token.pickle stores the user's access and refresh tokens
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not CLIENT_SECRETS_FILE.exists():
                print(f"Error: {CLIENT_SECRETS_FILE} not found!")
                print("Please follow these steps:")
                print("1. Go to Google Cloud Console")
                print("2. Create a project and enable YouTube Data API")
                print("3. Configure OAuth consent screen")
                print("4. Create OAuth 2.0 credentials")
                print(f"5. Download and place in {CLIENT_SECRETS_FILE}")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_FILE), SCOPES)
            credentials = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)

    return credentials

def datetime_to_iso(dt):
    """Convert datetime to ISO format string"""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt

def load_titles():
    """Load titles from shorts_titles.json"""
    try:
        # Load and normalize output folder from config
        config_path = project_root / "config" / "master_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            output_root = Path(config['output_folder']).expanduser().resolve()
        
        titles_path = output_root / "shorts_titles.json"
        with open(titles_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: shorts_titles.json not found!")
        return {}
    except json.JSONDecodeError:
        print("Error: Invalid JSON in shorts_titles.json!")
        return {}

def normalize_path(path):
    """Normalize path to use forward slashes and handle both Windows and Unix paths"""
    # Convert to Path object first to handle any path format
    path_obj = Path(path)
    # If it's an absolute path, make it relative to project root
    if path_obj.is_absolute():
        try:
            path_obj = path_obj.relative_to(project_root)
        except ValueError:
            pass  # If path is not under project root, keep it as is
    # Convert to string with forward slashes
    return str(path_obj).replace('\\', '/')

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

def update_upload_status(video_path: str, video_id: str):
    """Update the upload status in both shorts_titles.json and metadata files"""
    # Update shorts_titles.json
    titles_path = project_root / "output" / "shorts_titles.json"
    if titles_path.exists():
        try:
            with open(titles_path, 'r', encoding='utf-8') as f:
                titles = json.load(f)
            
            # Normalize the video path
            rel_path = normalize_path(video_path)
            
            if rel_path in titles:
                titles[rel_path]["uploaded"] = True
                titles[rel_path]["upload_date"] = datetime.now(pytz.UTC).isoformat()
                titles[rel_path]["youtube_id"] = video_id
                
                with open(titles_path, 'w', encoding='utf-8') as f:
                    json.dump(titles, f, indent=2, ensure_ascii=False)
                print(f"Updated upload status in shorts_titles.json for {video_path}")
        except Exception as e:
            print(f"Error updating shorts_titles.json: {str(e)}")

    # Update metadata file
    try:
        # Find the corresponding metadata file
        metadata_dir = project_root / "output" / "metadata"
        video_name = Path(video_path).stem
        metadata_files = list(metadata_dir.glob(f"{video_name}.json"))
        
        if metadata_files:
            metadata_file = metadata_files[0]
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            metadata["uploaded"] = True
            metadata["upload_date"] = datetime.now(pytz.UTC).isoformat()
            metadata["youtube_id"] = video_id
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            print(f"Updated upload status in metadata file for {video_path}")
    except Exception as e:
        print(f"Error updating metadata file: {str(e)}")

def upload_shorts():
    """Upload all shorts in the output directory to YouTube."""
    try:
        # Get output directory from config
        with open('config/master_config.json', 'r') as f:
            config = json.load(f)
            output_folder = config.get('output_folder', 'output')
        
        # Get all shorts in the output directory
        shorts_dir = Path(output_folder) / 'shorts'
        if not shorts_dir.exists():
            print(f"No shorts directory found at {shorts_dir}")
            return
        
        # Get all mp4 files
        shorts = list(shorts_dir.glob('*.mp4'))
        if not shorts:
            print("No shorts found to upload")
            return
        
        print(f"Found {len(shorts)} shorts to upload")
        
        # Load schedule config
        schedule_config = ScheduleConfig()
        
        # Get current time in UTC
        current_time = datetime.now(pytz.UTC)
        
        # Process each short
        for short_path in shorts:
            try:
                # Get metadata from JSON file in the metadata directory
                metadata_dir = Path(output_folder) / 'metadata'
                # Remove _with_subs from the filename if present
                base_name = short_path.stem.replace('_with_subs', '')
                json_path = metadata_dir / (base_name + '.json')
                print(f"Looking for metadata at: {json_path}")
                if not json_path.exists():
                    print(f"No metadata found for {short_path.name}")
                    continue
                
                with open(json_path, 'r') as f:
                    metadata = json.load(f)
                
                # Get next available publish time
                publish_time = schedule_config.get_next_publish_time(current_time)
                if not publish_time:
                    print("No available publish times in schedule")
                    continue
                
                # Upload the short
                video_id = upload_to_youtube(
                    video_path=str(short_path),
                    title=metadata['title'],
                    description=metadata.get('description', ''),
                    tags=metadata.get('tags', []),
                    thumbnail_path=str(short_path.with_suffix('.jpg')) if short_path.with_suffix('.jpg').exists() else None,
                    publish_time=publish_time
                )
                
                if video_id:
                    # Update metadata with upload info
                    metadata['uploaded'] = True
                    metadata['video_id'] = video_id
                    metadata['upload_date'] = current_time.isoformat()
                    metadata['publish_time'] = publish_time.isoformat()
                    
                    # Save updated metadata
                    with open(json_path, 'w') as f:
                        json.dump(metadata, f, indent=2)
                    
                    print(f"Successfully uploaded {short_path.name}")
                else:
                    print(f"Failed to upload {short_path.name}")
                
            except Exception as e:
                print(f"Error processing {short_path.name}: {str(e)}")
                continue
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

if __name__ == "__main__":
    upload_shorts() 