#TLDR
1. pip install -r requirements.txt
2. paste client_secrets.json & create config.env in root/config
   OPENROUTER_API_KEY=
   DEEPGRAM_API_KEY=
3. Run src/auth_youtube.py #to integrate Youtube (generates token.pickle in /config) [one time process only should be done to change youtube account]
4. Set input & outfolder /config/master_config.json (I/O Folder, scheduling time, Boolean for pipeline   steps)  # make sure to save else wont work
5. Run  run_pipeline.py                    # Print("TA-DA") only if it works.

(individual scripts are in Src dir) 

## Prerequisites

- Python 3.8 or higher
- FFmpeg installed on your system
- Google Cloud account with YouTube Data API enabled
- OpenRouter API key
- Deepgram API key

## Step-by-Step Setup Guide

1. **Clone the Repository**
   ```bash
   git clone [repository-url]
   cd automationtool
   ```

2. **Create and Activate Virtual Environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Google Cloud Setup**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable YouTube Data API v3
   - Configure OAuth consent screen:
     - Set application type as "Desktop app"
     - Add necessary scopes:
       - https://www.googleapis.com/auth/youtube.upload
       - https://www.googleapis.com/auth/youtube
   - Create OAuth 2.0 credentials
   - Download credentials and save as `client_secrets.json` in the `config/` directory

5. **Environment Configuration**
   - Navigate to `config/config.env`
   - Update the following variables:
     ```
     OPENROUTER_API_KEY=your_openrouter_api_key
     DEEPGRAM_API_KEY=your_deepgram_api_key
     ```
   - Note: These API keys are required for:
     - OpenRouter: Used for AI-powered title generation
     - Deepgram: Used for video transcription and silence detection

6. **Configure Pipeline Settings**
   - Navigate to `config/master_config.json`
   - Update the configuration according to your needs:
     - Video processing settings
     - Upload schedules
     - Output directories
     - API endpoints

## Running the Pipeline

1. **Basic Pipeline Execution**
   ```bash
   python run_pipeline.py
   ```

2. **Pipeline with Custom Configuration**
   ```bash
   python run_pipeline.py --config path/to/config.json
   ```

3. **Pipeline Logging**
   - Pipeline logs are stored in `pipeline.log`
   - Check this file for detailed execution information and any errors

## Module Features

1. **Title Generator (`title_generator.py`)**
   - AI-powered title generation using OpenRouter
   - Customizable title formats
   - SEO optimization suggestions

2. **Transcription (`transcription.py`)**
   - Automatic video transcription using Deepgram
   - Multiple language support
   - Subtitle file generation

3. **Silence Trimmer (`silence_trimmer.py`)**
   - Automatic silence detection
   - Configurable silence thresholds
   - Smart trimming algorithms

4. **Subtitle Clipper (`subtitle_clipper.py`)**
   - Subtitle synchronization
   - Format conversion
   - Timing adjustments

5. **Schedule Config (`schedule_config.py`)**
   - Advanced scheduling capabilities
   - Multiple timezone support
   - Batch upload scheduling

## Output Structure

The `output/` directory contains:
- Processed video files
- Generated thumbnails
- Metadata files
- Temporary processing files
- Subtitle files
- Log files

## Security Best Practices

1. **API Credentials**
   - Never commit `client_secrets.json` or `config.env` to version control
   - Keep your OAuth tokens secure
   - Regularly rotate your API credentials

2. **Environment Variables**
   - Use environment variables for sensitive data
   - Keep `config.env` file secure and local

3. **Access Control**
   - Restrict access to the project directory
   - Use appropriate file permissions

## Troubleshooting

1. **Authentication Issues**
   - Verify your Google Cloud credentials
   - Check if the OAuth consent screen is properly configured
   - Ensure all required scopes are enabled
   - If token.pickle is corrupted, delete it and re-authenticate

2. **Pipeline Errors**
   - Check `pipeline.log` for detailed error messages
   - Verify all dependencies are correctly installed
   - Ensure FFmpeg is properly installed and accessible
   - Verify API keys are correctly set in `config.env`

3. **Common Issues**
   - If video upload fails, check your internet connection
   - If transcription fails, verify Deepgram API key
   - If title generation fails, verify OpenRouter API key
   - If subtitle processing fails, check file formats and encoding

## Support

For issues and feature requests, please:
1. Check the existing issues
2. Create a new issue with detailed information
3. Include relevant logs and error messages

## License

MIT License