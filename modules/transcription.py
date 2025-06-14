import os
import json
import subprocess
import shutil
from pathlib import Path
from deepgram import Deepgram
import asyncio
from dotenv import load_dotenv

class TranscriptionHandler:
    def __init__(self):
        # Load environment variables
        project_root = Path(__file__).parent.parent
        load_dotenv(project_root / "config" / "config.env")
        
        # Initialize Deepgram client
        self.dg_client = Deepgram(os.getenv('DEEPGRAM_API_KEY'))
        
        # Load and normalize output folder from config
        config_path = project_root / "config" / "master_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            self.output_root = Path(config['output_folder']).expanduser().resolve()
        
        self.subtitles_dir = self.output_root / "subtitles"
        
        # Create directories if they don't exist
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.subtitles_dir.mkdir(parents=True, exist_ok=True)
    
    async def _transcribe_with_deepgram(self, video_path):
        """Transcribe a video file using Deepgram API."""
        with open(video_path, 'rb') as audio:
            source = {'buffer': audio, 'mimetype': 'video/mp4'}
            options = {
                'punctuate': True,
                'model': 'nova-2',
                'language': 'en',
                'smart_format': True
            }
            
            response = await self.dg_client.transcription.prerecorded(source, options)
            return response
    
    def transcribe_video(self, video_path):
        """Transcribe a video file and save subtitles."""
        print(f"Transcribing: {video_path}")
        
        # Get the video filename without extension
        video_name = Path(video_path).stem
        srt_path = self.subtitles_dir / f"{video_name}.srt"
        
        # Run async transcription
        response = asyncio.run(self._transcribe_with_deepgram(str(video_path)))
        
        # Convert Deepgram response to our segment format
        segments = []
        for word in response['results']['channels'][0]['alternatives'][0]['words']:
            segment = {
                'start': word['start'],
                'end': word['end'],
                'text': word['punctuated_word'] if 'punctuated_word' in word else word['word']
            }
            segments.append(segment)
        
        # Group words into sentences for better subtitle formatting
        formatted_segments = self._group_words_into_sentences(segments)
        
        # Save subtitles
        self._save_srt(formatted_segments, srt_path)
        print(f"Subtitles saved to: {srt_path}")
        
        return srt_path
    
    def _group_words_into_sentences(self, segments, max_duration=5.0):
        """Group words into sentences for better subtitle formatting."""
        formatted_segments = []
        current_segment = {
            'start': segments[0]['start'],
            'end': segments[0]['end'],
            'text': segments[0]['text']
        }
        
        for i in range(1, len(segments)):
            current_word = segments[i]
            
            # If adding this word would make the segment too long, start a new segment
            if current_word['end'] - current_segment['start'] > max_duration:
                formatted_segments.append(current_segment)
                current_segment = {
                    'start': current_word['start'],
                    'end': current_word['end'],
                    'text': current_word['text']
                }
            else:
                # Add word to current segment
                current_segment['end'] = current_word['end']
                current_segment['text'] += ' ' + current_word['text']
        
        # Add the last segment
        if current_segment:
            formatted_segments.append(current_segment)
        
        return formatted_segments
    
    def _save_srt(self, segments, path):
        """Save transcription segments as SRT file."""
        def format_timestamp(seconds):
            hrs = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"
        
        with open(path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(segments, 1):
                start = format_timestamp(segment['start'])
                end = format_timestamp(segment['end'])
                text = segment['text'].strip()
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
    
    def _convert_srt_to_ass(self, srt_path):
        """Convert SRT file to ASS format using FFmpeg."""
        srt_path = Path(srt_path)
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_path}")
        
        ass_path = srt_path.with_suffix('.ass')
        
        # Use forward slashes for FFmpeg paths
        srt_path_str = str(srt_path).replace('\\', '/')
        ass_path_str = str(ass_path).replace('\\', '/')
        
        # Build the FFmpeg command to convert SRT to ASS
        cmd = [
            "ffmpeg",
            "-i", srt_path_str,
            ass_path_str
        ]
        
        try:
            print(f"Converting {srt_path} to ASS format...")
            print("Running command:", " ".join(cmd))
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                print("FFmpeg Error Output:")
                print(result.stderr)
                raise Exception("FFmpeg failed to convert SRT to ASS")
            
            if not ass_path.exists():
                raise Exception(f"ASS file was not created at {ass_path}")
                
            print(f"Successfully converted to {ass_path}")
            return ass_path
        except Exception as e:
            print(f"Error during SRT to ASS conversion: {str(e)}")
            raise 