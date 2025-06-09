import whisper
import os
import subprocess
import shutil
from pathlib import Path

class TranscriptionHandler:
    def __init__(self):
        self.model = whisper.load_model("base")
        self.output_dir = Path("output")
        self.subtitles_dir = self.output_dir / "subtitles"
        
        # Create directories if they don't exist
        self.output_dir.mkdir(exist_ok=True)
        self.subtitles_dir.mkdir(exist_ok=True)
    
    def transcribe_video(self, video_path):
        """Transcribe a video file and save subtitles."""
        print(f"Transcribing: {video_path}")
        
        # Get the video filename without extension
        video_name = Path(video_path).stem
        srt_path = self.subtitles_dir / f"{video_name}.srt"
        
        # Transcribe the video
        result = self.model.transcribe(str(video_path))
        
        # Save subtitles
        self._save_srt(result["segments"], srt_path)
        print(f"Subtitles saved to: {srt_path}")
        
        return srt_path
    
    def _save_srt(self, segments, path):
        """Save transcription segments as SRT file."""
        def format_timestamp(seconds):
            hrs = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

        # Use utf-8 without BOM for better FFmpeg compatibility
        with open(path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(segments):
                start = format_timestamp(seg['start'])
                end = format_timestamp(seg['end'])
                text = seg['text'].strip().title()
                
                # Split text into words and format into max 2 lines with 2 words each
                words = text.split()
                formatted_lines = []
                for i in range(0, min(len(words), 4), 2):  # Process max 4 words (2 lines × 2 words)
                    line = ' '.join(words[i:i+2])
                    formatted_lines.append(line)
                
                formatted_text = '\n'.join(formatted_lines)
                f.write(f"{i+1}\n{start} --> {end}\n{formatted_text}\n\n")
    
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