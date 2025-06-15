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
from typing import List, Optional
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Add the project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from modules.upload_youtube import upload_to_youtube, upload_with_schedule
from modules.schedule_config import ScheduleConfig
from config.youtube_config import YOUTUBE_API_SCOPES, TOKEN_FILE, CLIENT_SECRETS_FILE

logger = logging.getLogger(__name__)

# Define the scopes
SCOPES = YOUTUBE_API_SCOPES

def get_authenticated_service():
    """Get authenticated YouTube service"""
    credentials = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not CLIENT_SECRETS_FILE.exists():
                logger.error(f"Error: {CLIENT_SECRETS_FILE} not found!")
                logger.error("Please follow these steps:")
                logger.error("1. Go to Google Cloud Console")
                logger.error("2. Create a project and enable YouTube Data API")
                logger.error("3. Configure OAuth consent screen")
                logger.error("4. Create OAuth 2.0 credentials")
                logger.error(f"5. Download and place in {CLIENT_SECRETS_FILE}")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_FILE), SCOPES)
            credentials = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)
    return credentials

def datetime_to_iso(dt):
    """Convert datetime to ISO format string"""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt

def load_titles():
    """Load titles and metadata from shorts_titles.json."""
    try:
        # Get output directory from master config
        with open('config/master_config.json', 'r') as f:
            master_config = json.load(f)
            output_folder = Path(master_config.get('output_folder', 'output')).expanduser().resolve()
        
        # Try to load from output directory
        titles_file = output_folder / "shorts_titles.json"
        if not titles_file.exists():
            logger.warning(f"shorts_titles.json not found at {titles_file}")
            return {}
        
        with open(titles_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Successfully loaded metadata for {len(data)} videos from {titles_file}")
            
            # Validate metadata structure and clean up quotes
            valid_data = {}
            for path, info in data.items():
                if not isinstance(info, dict):
                    logger.warning(f"Invalid metadata format for {path}, skipping")
                    continue
                    
                # Clean up quotes from title and description
                if 'title' in info:
                    info['title'] = info['title'].strip('"').strip("'")  # Remove both single and double quotes
                if 'description' in info:
                    info['description'] = info['description'].strip('"').strip("'")  # Remove both single and double quotes
                
                # Clean up hashtags - ensure no duplicate # symbols
                if 'hashtags' in info:
                    info['hashtags'] = [tag.strip('#') for tag in info['hashtags']]
                
                # Ensure all required fields exist
                if not info.get('title'):
                    logger.warning(f"No title found for {path}, using filename as title")
                    info['title'] = Path(path).stem
                
                if not info.get('hashtags'):
                    logger.warning(f"No hashtags found for {path}, using default hashtags")
                    info['hashtags'] = ["shorts", "viral"]
                
                if not info.get('description'):
                    logger.warning(f"No description found for {path}, using default description")
                    info['description'] = f"Check out this amazing short video! {info['title']}"
                
                valid_data[path] = info
            
            # Log sample metadata for debugging
            for path, info in list(valid_data.items())[:3]:
                logger.info(f"Sample metadata for {path}:")
                logger.info(f"  Title: {info.get('title', 'No title')}")
                logger.info(f"  Hashtags: {info.get('hashtags', [])}")
                logger.info(f"  Description: {info.get('description', 'No description')[:100]}...")
            
            return valid_data
    except json.JSONDecodeError:
        logger.error(f"Error parsing {titles_file}. Using default titles.")
        return {}
    except Exception as e:
        logger.error(f"Error loading titles: {str(e)}")
        return {}

def normalize_path(path: str) -> str:
    """Normalize path to match the format in shorts_titles.json."""
    try:
        # Load output folder from config
        with open('config/master_config.json', 'r') as f:
            master_config = json.load(f)
            output_folder = Path(master_config.get('output_folder', 'output')).expanduser().resolve()
        
        # Convert to absolute path
        abs_path = Path(path).resolve()
        
        # Try to get relative path from output directory
        try:
            rel_path = str(abs_path.relative_to(output_folder))
            return rel_path.replace('\\', '/')
        except ValueError:
            # If path is not in output directory, use the filename
            return abs_path.name
            
    except Exception as e:
        logger.error(f"Error normalizing path {path}: {str(e)}")
        return str(Path(path).name)  # Fallback to just the filename

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
    # Load and normalize output folder from config
    config_path = project_root / "config" / "master_config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        output_root = Path(config['output_folder']).expanduser().resolve()
    
    # Update shorts_titles.json
    titles_path = output_root / "shorts_titles.json"
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
                logger.info(f"Updated upload status in shorts_titles.json for {video_path}")
        except Exception as e:
            logger.error(f"Error updating shorts_titles.json: {str(e)}")

    # Update metadata file
    try:
        # Find the corresponding metadata file
        metadata_dir = output_root / "metadata"
        video_name = Path(video_path).stem
        metadata_file = metadata_dir / f"{video_name}.json"
        
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            metadata["uploaded"] = True
            metadata["upload_date"] = datetime.now(pytz.UTC).isoformat()
            metadata["youtube_id"] = video_id
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            logger.info(f"Updated upload status in metadata file for {video_path}")
    except Exception as e:
        logger.error(f"Error updating metadata file: {str(e)}")

def upload_with_schedule(video_path: str, title: str, description: str, tags: List[str], schedule_config: ScheduleConfig, schedule_time: datetime) -> Optional[str]:
    """Upload a video to YouTube with scheduling."""
    try:
        # Get credentials
        credentials = get_authenticated_service()
        if not credentials:
            logger.error("Failed to get YouTube credentials")
            return None
            
        # Create YouTube service
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Prepare video metadata
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '22'  # People & Blogs category
            },
            'status': {
                'privacyStatus': 'private',
                'publishAt': schedule_time.isoformat(),
                'selfDeclaredMadeForKids': False
            }
        }
        
        # Upload video
        logger.info(f"Uploading video: {title}")
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True)
        )
        
        response = request.execute()
        video_id = response.get('id')
        
        if video_id:
            logger.info(f"Video uploaded successfully! Video ID: {video_id}")
            logger.info(f"Scheduled for: {schedule_time.strftime('%Y-%m-%dT%H:%M:%SZ')}")
            return video_id
        else:
            logger.error("Failed to get video ID from upload response")
            return None
            
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        return None

def upload_shorts():
    """Upload all shorts in the output directory to YouTube."""
    try:
        logger.info("\n=== Starting YouTube Shorts Upload Process ===")
        
        # Get output directory and schedule config from master config
        with open('config/master_config.json', 'r') as f:
            master_config = json.load(f)
            output_folder = Path(master_config.get('output_folder', 'output')).expanduser().resolve()
        
        # Get credentials and initialize schedule config
        credentials = get_authenticated_service()
        if not credentials:
            logger.error("Failed to get YouTube credentials. Please ensure you have set up the YouTube API credentials correctly.")
            return
            
        schedule_config = ScheduleConfig(
            config_file='config/master_config.json',
            credentials=credentials
        )
        
        # Get all shorts in the output directory
        shorts_dir = output_folder / 'shorts'
        if not shorts_dir.exists():
            logger.error(f"No shorts directory found at {shorts_dir}")
            return
        
        # Get all mp4 files
        shorts = list(shorts_dir.glob('*.mp4'))
        if not shorts:
            logger.warning("No shorts found to upload")
            return
        
        # Load titles and metadata
        titles_data = load_titles()
        if not titles_data:
            logger.warning("No metadata found. Will use default titles and descriptions.")
        
        logger.info(f"\nFound {len(shorts)} shorts to upload")
        
        # Prepare video metadata for scheduling
        video_metadata = []
        for short in shorts:
            # Get metadata from shorts_titles.json
            short_path = normalize_path(str(short))
            short_info = titles_data.get(short_path, {})
            if not short_info:
                # Try alternative path formats
                alt_paths = [
                    f"shorts/{short.name}",
                    str(short.relative_to(output_folder)),
                    str(short.name)
                ]
                for alt_path in alt_paths:
                    if alt_path in titles_data:
                        short_info = titles_data[alt_path]
                        break
            
            # Clean up quotes from title and description
            if 'title' in short_info:
                short_info['title'] = short_info['title'].strip('"').strip("'")  # Remove both single and double quotes
            if 'description' in short_info:
                short_info['description'] = short_info['description'].strip('"').strip("'")  # Remove both single and double quotes
            
            # Clean up hashtags - ensure no duplicate # symbols
            if 'hashtags' in short_info:
                short_info['hashtags'] = [tag.strip('#') for tag in short_info['hashtags']]
            
            # Get title, description, and tags with fallbacks
            title = short_info.get('title', short.stem)
            description = short_info.get('description', '')
            tags = short_info.get('hashtags', [])
            
            # Validate metadata before upload
            if not title:
                title = short.stem
            if not tags:
                tags = ["shorts", "viral"]
            if not description:
                description = f"Check out this amazing short video! {title}"
            
            video_metadata.append({
                'title': title,
                'description': description,
                'tags': tags,
                'path': str(short)
            })
        
        # Get schedule for all videos at once
        schedules = schedule_config.get_schedule_for_videos(len(shorts), video_metadata=video_metadata)
        if not schedules:
            logger.error("Failed to generate schedule for videos")
            return
        
        # Process each short
        successful_uploads = 0
        failed_uploads = 0
        
        for schedule_item in schedules:
            try:
                video_path = schedule_item['metadata']['path']
                title = schedule_item['title']
                description = schedule_item['metadata']['description']
                tags = schedule_item['metadata']['tags']
                schedule_time = schedule_item['scheduled_time']
                
                logger.info(f"\nUploading video: {title}")
                
                # Upload with schedule
                video_id = upload_with_schedule(
                    video_path=video_path,
                    title=title,
                    description=description,
                    tags=tags,
                    schedule_config=schedule_config,
                    schedule_time=schedule_time
                )
                
                if video_id:
                    logger.info(f"Video uploaded successfully! Video ID: {video_id}")
                    logger.info(f"Scheduled for: {schedule_time.strftime('%Y-%m-%dT%H:%M:%SZ')}")
                    update_upload_status(video_path, video_id)
                    # Update the schedule item with the video ID
                    schedule_item['metadata']['youtube_id'] = video_id
                    successful_uploads += 1
                else:
                    logger.error(f"Failed to upload {Path(video_path).name}")
                    failed_uploads += 1
                    
            except Exception as e:
                logger.error(f"Error uploading {Path(video_path).name}: {str(e)}")
                failed_uploads += 1
                
        # After all uploads are complete, display final schedule with video IDs
        logger.info("\n📅  Final Schedule:")
        for schedule_item in schedules:
            video_id = schedule_item['metadata'].get('youtube_id', 'Not uploaded yet')
            logger.info(f"📤  \"{schedule_item['title']}\" → {schedule_item['scheduled_time'].strftime('%Y-%m-%d %H:%M')} {schedule_config.timezone.zone} [ID: {video_id}]")

        logger.info(f"\nUpload Summary:")
        logger.info(f"Successfully uploaded: {successful_uploads}")
        logger.info(f"Failed uploads: {failed_uploads}")
        
        # Load and display final metadata from shorts_titles.json
        try:
            titles_file = output_folder / "shorts_titles.json"
            if titles_file.exists():
                with open(titles_file, 'r', encoding='utf-8') as f:
                    titles_data = json.load(f)
                
                logger.info("\n📋  Final Metadata Summary:")
                for path, info in titles_data.items():
                    if info.get('uploaded'):
                        video_id = info.get('youtube_id', 'Unknown')
                        title = info.get('title', 'No title')
                        upload_date = info.get('upload_date', 'Unknown')
                        logger.info(f"🎥  Video ID: {video_id}")
                        logger.info(f"📝  Title: {title}")
                        logger.info(f"📅  Upload Date: {upload_date}")
                        logger.info("---")
        except Exception as e:
            logger.error(f"Error reading final metadata: {str(e)}")
        
        # Add completion message after metadata summary
        logger.info("✅  Completed: Step 4: Upload shorts and schedule")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    upload_shorts() 