import os
from modules.schedule_config import ScheduleConfig
from modules.upload_youtube import upload_to_youtube
from datetime import datetime, timedelta
import pytz
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

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
                'credentials', SCOPES)  # Use the renamed file
            credentials = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(credentials, token)

    return credentials

# Get authenticated credentials
credentials = get_authenticated_service()

# Create an instance of ScheduleConfig with the credentials
config = ScheduleConfig(credentials=credentials)

def main():
    # Get the list of videos from the videos directory
    video_dir = 'videos'
    video_files = [os.path.join(video_dir, f) for f in os.listdir(video_dir) if f.endswith('.mp4')]
    
    # Simulate scheduling for the videos
    schedule = config.get_schedule_for_videos(len(video_files))
    
    print("\n=== Upload Schedule Test ===")
    print(f"Number of videos to schedule: {len(video_files)}")
    print(f"Current timezone: {config.timezone.zone}")
    print(f"Current time: {config.get_current_time().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    print("\n=== Schedule Details ===")
    print("=" * 80)
    print(f"{'Video':<20} {'Scheduled Date':<15} {'Scheduled Time (IST)':<20} {'UTC Time':<20}")
    print("-" * 80)
    
    for video_path, publish_time in zip(video_files, schedule):
        local_time = publish_time.astimezone(config.timezone)
        print(f"{os.path.basename(video_path):<20} {local_time.strftime('%Y-%m-%d'):<15} "
              f"{local_time.strftime('%I:%M %p'):<20} "
              f"{publish_time.strftime('%Y-%m-%d %H:%M %Z'):<20}")
    
    print("=" * 80)
    
    # Validate the schedule
    print("\n=== Schedule Validation ===")
    if config.validate_schedule(schedule):
        print("✅ Schedule is valid")
        print("✅ Videos are properly distributed across days")
        print("✅ Minimum interval between uploads is maintained")
        print("✅ Maximum videos per week limit is respected")
    else:
        print("❌ Schedule validation failed")
    
    # Print day-wise distribution
    print("\n=== Day-wise Distribution ===")
    day_counts = {}
    for time in schedule:
        local_time = time.astimezone(config.timezone)
        day = local_time.strftime('%A')
        day_counts[day] = day_counts.get(day, 0) + 1
    
    for day, count in sorted(day_counts.items()):
        print(f"{day:<10}: {count} video(s)")
    
    # Upload videos to YouTube with scheduled times
    print("\n=== Uploading Videos to YouTube ===")
    for video_path, publish_time in zip(video_files, schedule):
        # Ensure publish_time is within YouTube's allowed range (at least 15 minutes in the future, not more than 6 months)
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

        title = os.path.basename(video_path).replace('.mp4', '')
        description = f"Scheduled upload for {title}"
        tags = ["scheduled", "automated"]
        video_id = upload_to_youtube(video_path, title, description, tags, publish_time=publish_time_str)
        if video_id:
            print(f"✅ Uploaded {title} (Video ID: {video_id})")
        else:
            print(f"❌ Failed to upload {title}")

if __name__ == "__main__":
    main() 