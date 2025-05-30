from modules.upload_youtube import upload_to_youtube
import datetime

def test_upload():
    # Test video details
    video_path = "test_video.mp4"  # Replace with your video path
    title = "My First Automated Upload"
    description = "This is a test upload using the YouTube API"
    tags = ["test", "automation", "python", "youtube api"]
    
    # Schedule for tomorrow
    publish_time = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat() + "Z"
    
    # Upload the video
    video_id = upload_to_youtube(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        publish_time=publish_time
    )
    
    if video_id:
        print(f"Success! Video will be published at: {publish_time}")
        print(f"You can view it here: https://youtube.com/watch?v={video_id}")
    else:
        print("Upload failed. Check the error messages above.")

if __name__ == "__main__":
    test_upload() 