import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# YouTube API Configuration
YOUTUBE_API_SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
                      'https://www.googleapis.com/auth/youtube']

# Default upload settings
DEFAULT_VIDEO_CATEGORY = os.getenv('DEFAULT_VIDEO_CATEGORY', '22')  # People & Blogs
DEFAULT_PRIVACY_STATUS = os.getenv('DEFAULT_PRIVACY_STATUS', 'private')

# File paths
TOKEN_FILE = 'token.pickle'
CLIENT_SECRETS_FILE = 'client_secrets.json'

# Video settings
MAX_VIDEO_LENGTH = 60  # seconds
SUPPORTED_VIDEO_FORMATS = ['.mp4', '.mov', '.avi']
SUPPORTED_THUMBNAIL_FORMATS = ['.jpg', '.jpeg', '.png'] 