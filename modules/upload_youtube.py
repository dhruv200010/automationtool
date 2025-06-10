import os
import datetime
import pytz
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle
import sys
from pathlib import Path

# Get project root directory
project_root = Path(__file__).parent.parent

# Import from config directory
from config.youtube_config import (
    YOUTUBE_API_SCOPES,
    DEFAULT_VIDEO_CATEGORY,
    DEFAULT_PRIVACY_STATUS,
    TOKEN_FILE,
    CLIENT_SECRETS_FILE,
    SUPPORTED_VIDEO_FORMATS,
    SUPPORTED_THUMBNAIL_FORMATS
)

def get_authenticated_service():
    """
    Authenticate with YouTube API and return the service object.
    This function handles the OAuth2 flow and token management.
    """
    credentials = None
    
    # Check if client_secrets.json exists
    client_secrets_path = project_root / CLIENT_SECRETS_FILE
    if not client_secrets_path.exists():
        print(f"Error: {client_secrets_path} not found!")
        print("Please follow these steps:")
        print("1. Go to Google Cloud Console")
        print("2. Create a project and enable YouTube Data API")
        print("3. Configure OAuth consent screen")
        print("4. Create OAuth 2.0 credentials")
        print(f"5. Download and rename to {client_secrets_path}")
        sys.exit(1)
    
    # Check if we have stored credentials
    token_path = project_root / TOKEN_FILE
    if token_path.exists():
        with open(token_path, 'rb') as token:
            credentials = pickle.load(token)
    
    # If credentials are invalid or don't exist, get new ones
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {str(e)}")
                print(f"Please delete {token_path} and try again")
                sys.exit(1)
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(client_secrets_path), YOUTUBE_API_SCOPES)
                credentials = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Error during authentication: {str(e)}")
                print("Please make sure you:")
                print("1. Have enabled YouTube Data API")
                print("2. Have configured OAuth consent screen")
                print("3. Have added your email as a test user")
                sys.exit(1)
        
        # Save credentials for future use
        with open(token_path, 'wb') as token:
            pickle.dump(credentials, token)
    
    return build('youtube', 'v3', credentials=credentials)

def validate_file(file_path, file_type='video'):
    """Validate if file exists and has correct format"""
    path = Path(file_path)
    if not path.exists():
        return False, f"File not found: {file_path}"
    
    ext = path.suffix.lower()
    if file_type == 'video' and ext not in SUPPORTED_VIDEO_FORMATS:
        return False, f"Unsupported video format: {ext}"
    elif file_type == 'thumbnail' and ext not in SUPPORTED_THUMBNAIL_FORMATS:
        return False, f"Unsupported thumbnail format: {ext}"
    
    return True, None

def upload_to_youtube(video_path, title, description, tags, thumbnail_path=None, publish_time=None):
    """
    Upload a video to YouTube with scheduling.
    
    Args:
        video_path (str): Path to the video file
        title (str): Video title
        description (str): Video description
        tags (list): List of tags
        thumbnail_path (str, optional): Path to thumbnail image
        publish_time (datetime or str, optional): Datetime object or ISO format string for scheduling
    """
    try:
        # Validate video file
        is_valid, error_msg = validate_file(video_path, 'video')
        if not is_valid:
            print(f"Error: {error_msg}")
            return None

        # Get authenticated YouTube service
        youtube = get_authenticated_service()
        
        # Prepare video metadata
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': DEFAULT_VIDEO_CATEGORY
            },
            'status': {
                'privacyStatus': DEFAULT_PRIVACY_STATUS,
                'selfDeclaredMadeForKids': False
            }
        }
        
        # If publish time is provided, format it properly for YouTube API
        if publish_time:
            # Convert to UTC if it's a datetime object
            if isinstance(publish_time, datetime.datetime):
                if publish_time.tzinfo is None:
                    publish_time = publish_time.replace(tzinfo=datetime.UTC)
                else:
                    publish_time = publish_time.astimezone(datetime.UTC)
                # Format as ISO 8601 with 'Z' suffix
                publish_time = publish_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            # If it's already a string, ensure it ends with 'Z'
            elif isinstance(publish_time, str) and not publish_time.endswith('Z'):
                publish_time = publish_time + 'Z'
            
            # Ensure the time is in the future
            now = datetime.datetime.now(datetime.UTC)
            publish_dt = datetime.datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
            if publish_dt <= now:
                print("Warning: Publish time is in the past. Using current time + 1 hour.")
                publish_time = (now + datetime.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            body['status']['publishAt'] = publish_time
        
        # Create the video upload request
        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True
        )
        
        # Upload the video
        print(f"Uploading video: {title}")
        video_response = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        ).execute()
        
        # If thumbnail is provided, upload it
        if thumbnail_path:
            is_valid, error_msg = validate_file(thumbnail_path, 'thumbnail')
            if is_valid:
                print("Uploading thumbnail...")
                youtube.thumbnails().set(
                    videoId=video_response['id'],
                    media_body=MediaFileUpload(thumbnail_path)
                ).execute()
            else:
                print(f"Warning: {error_msg}")
        
        print(f"Video uploaded successfully! Video ID: {video_response['id']}")
        if publish_time:
            print(f"Scheduled for: {publish_time}")
        
        return video_response['id']
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        if "quota" in str(e).lower():
            print("\nYou've exceeded your YouTube API quota.")
            print("Please wait 24 hours or create a new project.")
        return None

def upload_with_schedule(video_path, title, description, tags, thumbnail_path=None, schedule_config=None):
    """
    Upload a video to YouTube with automatic scheduling based on schedule config.
    
    Args:
        video_path (str): Path to the video file
        title (str): Video title
        description (str): Video description
        tags (list): List of tags
        thumbnail_path (str, optional): Path to thumbnail image
        schedule_config (ScheduleConfig, optional): Schedule configuration object
    """
    try:
        # Get next available publish time if schedule config is provided
        publish_time = None
        if schedule_config:
            current_time = datetime.datetime.now(pytz.UTC)
            publish_time = schedule_config.get_next_publish_time(current_time)
            if not publish_time:
                print("Warning: Could not find available schedule slot. Using default scheduling.")
                publish_time = current_time + datetime.timedelta(days=1)
        
        # Use the existing upload function with the calculated publish time
        return upload_to_youtube(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            thumbnail_path=thumbnail_path,
            publish_time=publish_time
        )
    except Exception as e:
        print(f"An error occurred during scheduled upload: {str(e)}")
        return None

if __name__ == "__main__":
    # Example usage
    video_path = "output/short_0.mp4"
    title = "Test Video"
    description = "This is a test video"
    tags = ["test", "youtube", "shorts"]
    publish_time = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)).isoformat() + "Z"
    
    upload_to_youtube(video_path, title, description, tags, publish_time=publish_time) 