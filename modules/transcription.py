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
                'smart_format': True,
                'utterances': True,  # Enable utterance detection
                'sentiment': True,   # Enable sentiment analysis
                'summarize': True    # Enable summarization
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
        
        # Convert Deepgram response to our segment format with scoring
        segments = []
        
        # Check if we have utterances or need to use words
        if 'utterances' in response['results']['channels'][0]['alternatives'][0]:
            # Use utterance-level data
            for utterance in response['results']['channels'][0]['alternatives'][0]['utterances']:
                segment = {
                    'start': utterance['start'],
                    'end': utterance['end'],
                    'text': utterance['transcript'],
                    'sentiment': utterance.get('sentiment', {}),
                    'confidence': utterance.get('confidence', 0),
                    'words': utterance.get('words', [])
                }
                segments.append(segment)
        else:
            # Use word-level data and group into sentences
            words = response['results']['channels'][0]['alternatives'][0]['words']
            current_segment = None
            
            for word in words:
                if current_segment is None:
                    current_segment = {
                        'start': word['start'],
                        'end': word['end'],
                        'text': word['punctuated_word'] if 'punctuated_word' in word else word['word'],
                        'sentiment': {},
                        'confidence': word.get('confidence', 0),
                        'words': [word]
                    }
                else:
                    # Check if we should start a new segment (e.g., on punctuation or long pause)
                    if (word.get('punctuated_word', '').endswith(('.', '!', '?')) or 
                        word['start'] - current_segment['end'] > 1.0):  # 1 second pause
                        segments.append(current_segment)
                        current_segment = {
                            'start': word['start'],
                            'end': word['end'],
                            'text': word['punctuated_word'] if 'punctuated_word' in word else word['word'],
                            'sentiment': {},
                            'confidence': word.get('confidence', 0),
                            'words': [word]
                        }
                    else:
                        # Add word to current segment
                        current_segment['end'] = word['end']
                        current_segment['text'] += ' ' + (word['punctuated_word'] if 'punctuated_word' in word else word['word'])
                        current_segment['words'].append(word)
                        current_segment['confidence'] = (current_segment['confidence'] + word.get('confidence', 0)) / 2
            
            # Add the last segment if it exists
            if current_segment:
                segments.append(current_segment)
        
        # Save subtitles with scoring information
        self._save_srt_with_scoring(segments, srt_path)
        print(f"Subtitles saved to: {srt_path}")
        
        return srt_path
    
    def _save_srt_with_scoring(self, segments, path):
        """Save transcription segments as SRT file with scoring information."""
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
                
                # Add scoring information as a comment
                sentiment = segment.get('sentiment', {})
                confidence = segment.get('confidence', 0)
                score = self._calculate_segment_score(segment)
                
                f.write(f"{i}\n{start} --> {end}\n{text}\n")
                f.write(f"# Score: {score:.2f}, Confidence: {confidence:.2f}, Sentiment: {sentiment}\n\n")
        
        # Save scoring data to a separate JSON file
        scoring_path = path.with_suffix('.json')
        with open(scoring_path, 'w', encoding='utf-8') as f:
            json.dump({
                'segments': [{
                    'start': s['start'],
                    'end': s['end'],
                    'text': s['text'],
                    'score': self._calculate_segment_score(s),
                    'sentiment': s.get('sentiment', {}),
                    'confidence': s.get('confidence', 0)
                } for s in segments]
            }, f, indent=2)
    
    def _calculate_segment_score(self, segment):
        """Calculate a score for a segment based on various factors."""
        score = 0.0
        
        # Base score from confidence
        confidence = segment.get('confidence', 0)
        score += confidence * 0.4  # 40% weight to confidence
        
        # Sentiment analysis
        sentiment = segment.get('sentiment', {})
        if sentiment:
            # Higher score for strong positive or negative sentiment
            sentiment_score = abs(sentiment.get('sentiment', 0))
            score += sentiment_score * 0.3  # 30% weight to sentiment
        
        # Length scoring (prefer segments between 15-30 seconds)
        duration = segment['end'] - segment['start']
        if 15 <= duration <= 30:
            score += 0.3  # 30% weight to optimal duration
        else:
            # Penalize segments that are too short or too long
            score += max(0, 0.3 - abs(duration - 22.5) * 0.02)  # 22.5 is the middle of 15-30 range
        
        return min(1.0, score)  # Normalize to 0-1 range
    
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