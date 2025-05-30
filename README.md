# YouTube Automation Tool

A Python tool for automating YouTube video uploads with scheduling capabilities.

## Features

- Upload videos to YouTube
- Schedule videos for future publication
- Add custom thumbnails
- Set video metadata (title, description, tags)
- Support for multiple video formats

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Google Cloud Setup**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable YouTube Data API v3
   - Configure OAuth consent screen
   - Create OAuth 2.0 credentials
   - Download credentials and rename to `client_secrets.json`

3. **Environment Setup**
   - Copy `.env.template` to `.env`
   - Update the values in `.env` with your credentials

## Usage

1. **Test Authentication**
   ```bash
   python test_auth.py
   ```

2. **Upload a Video**
   ```bash
   python test_upload.py
   ```

## Project Structure

```
.
├── modules/
│   └── upload_youtube.py    # YouTube upload functionality
├── config.py               # Configuration settings
├── .env.template          # Template for environment variables
├── .gitignore            # Git ignore file
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Security Notes

- Never commit `client_secrets.json` or `.env` to version control
- Keep your OAuth tokens secure
- Regularly rotate your API credentials

## License

MIT License 