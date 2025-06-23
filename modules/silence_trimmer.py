import os
import json
import subprocess
import tempfile
import ffmpeg
from pathlib import Path
import requests
from typing import List, Dict
import sys
import time

# Add the project root to Python path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add src directory to Python path
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add modules directory to Python path
modules_path = project_root / "modules"
if str(modules_path) not in sys.path:
    sys.path.insert(0, str(modules_path))

from dotenv import load_dotenv

class SilenceTrimmer:
    def __init__(self):
        # Load environment variables
        load_dotenv(project_root / "config" / "config.env")
        
        # Load and normalize output folder from config
        config_path = project_root / "config" / "master_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            self.output_root = Path(config['output_folder']).expanduser().resolve()
        
        self.processed_dir = self.output_root / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def extract_audio_from_video(self, video_path: str) -> str:
        """Extract audio from video for transcription"""
        try:
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio_path = temp_audio.name
            temp_audio.close()

            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(
                stream, temp_audio_path,
                format='wav',
                acodec='pcm_s16le',
                ac=1,
                ar='16000'
            )
            out, err = ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            return temp_audio_path
        except Exception as e:
            print(f"Error extracting audio from video: {e}")
            return None

    def transcribe_with_deepgram(self, audio_file_path: str, retries: int = 3, delay: int = 5) -> Dict:
        """Transcribe audio using Deepgram API with retry logic"""
        api_key = os.getenv('DEEPGRAM_API_KEY')
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY not found in environment variables")
       
        url = "https://api.deepgram.com/v1/listen"
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav"
        }
       
        for attempt in range(retries):
            try:
                with open(audio_file_path, "rb") as f:
                    f.seek(0)
                    response = requests.post(url, headers=headers, data=f)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error transcribing audio (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print("All retry attempts failed.")
                    return None
        return None

    def find_silence_segments(self, transcript_data: Dict, min_silence_duration: float = 0.5, buffer: float = 0.4) -> List[Dict]:
        """Find silence segments in the transcript"""
        words = transcript_data['results']['channels'][0]['alternatives'][0]['words']
        silence_segments = []
       
        for i in range(len(words) - 1):
            current_end = words[i]['end']
            next_start = words[i + 1]['start']
            silence_duration = next_start - current_end
           
            if silence_duration >= min_silence_duration:
                # Leave buffer at start and end of silence
                effective_start = current_end + buffer / 2
                effective_end = next_start - buffer / 2
                
                if effective_start < effective_end:
                    silence_segments.append({
                        'start': effective_start,
                        'end': effective_end,
                        'duration': effective_end - effective_start
                    })
       
        return silence_segments

    def create_trimmed_video(self, video_path: str, silence_segments: List[Dict], output_path: str) -> bool:
        """Create a video with silence segments removed"""
        try:
            # Create a temporary file to store the list of segments
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                current_time = 0
                for segment in silence_segments:
                    # Add segment before silence
                    if segment['start'] > current_time:
                        f.write(f"file '{video_path}'\n")
                        f.write(f"inpoint {current_time}\n")
                        f.write(f"outpoint {segment['start']}\n")
                    current_time = segment['end']
                
                # Add final segment if needed
                if current_time < self.get_video_duration(video_path):
                    f.write(f"file '{video_path}'\n")
                    f.write(f"inpoint {current_time}\n")
                    f.write(f"outpoint {self.get_video_duration(video_path)}\n")
                
                concat_file = f.name

            # Create the trimmed video
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-vsync', 'vfr',
                '-async', '1',
                '-af', 'aresample=async=1',
                '-strict', 'experimental',
                output_path
            ]
           
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            
            # Clean up temporary file
            os.unlink(concat_file)
            return True
           
        except Exception as e:
            print(f"Error creating trimmed video: {str(e)}")
            return False

    def get_video_duration(self, video_path: str) -> float:
        """Get the duration of a video file"""
        try:
            probe = ffmpeg.probe(video_path)
            return float(probe['format']['duration'])
        except Exception as e:
            print(f"Error getting video duration: {e}")
            return 0

    def process_video(self, video_path: str, buffer: float = 0.4) -> str:
        """Process a video to remove silence segments"""
        try:
            # Extract audio
            print("Extracting audio from video...")
            audio_path = self.extract_audio_from_video(video_path)
            if not audio_path:
                return None
           
            try:
                # Transcribe audio
                print("Transcribing audio...")
                transcript_data = self.transcribe_with_deepgram(audio_path)
                if not transcript_data:
                    return None
               
                # Find silence segments
                print("Finding silence segments...")
                silence_segments = self.find_silence_segments(transcript_data, buffer=buffer)
               
                # Create output path
                video_name = Path(video_path).stem
                output_path = self.processed_dir / f"{video_name}_trimmed.mp4"
               
                # Create trimmed video
                print("Creating trimmed video...")
                if self.create_trimmed_video(video_path, silence_segments, str(output_path)):
                    print(f"Created trimmed video: {output_path}")
                    return str(output_path)
                return None
               
            finally:
                # Clean up temporary audio file
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
                   
        except Exception as e:
            print(f"Error processing video: {str(e)}")
            return None 