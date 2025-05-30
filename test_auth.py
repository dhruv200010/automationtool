from modules.upload_youtube import get_authenticated_service

def test_auth():
    print("Testing YouTube API authentication...")
    try:
        youtube = get_authenticated_service()
        # Try to get channel info to verify authentication
        request = youtube.channels().list(
            part="snippet",
            mine=True
        )
        response = request.execute()
        
        if response and 'items' in response:
            channel_name = response['items'][0]['snippet']['title']
            print(f"✅ Authentication successful!")
            print(f"Connected to channel: {channel_name}")
            return True
        else:
            print("❌ Authentication failed: No channel data received")
            return False
            
    except Exception as e:
        print(f"❌ Authentication failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_auth() 