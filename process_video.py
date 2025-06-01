import sys
import subprocess
import shutil
from pathlib import Path
from modules.transcription import TranscriptionHandler

def run_command(cmd, description):
    """Run a command and print its output."""
    print(f"\n{description}...")
    print(f"Running: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print("Error Output:")
        print(result.stderr)
        raise Exception(f"Command failed: {' '.join(cmd)}")
    print("Success!")

def main():
    if len(sys.argv) != 2:
        print("Usage: python process_video.py <video_path>")
        print("Example: python process_video.py C:/Users/sendt/Downloads/long.MOV")
        sys.exit(1)
    
    video_path = sys.argv[1]
    video_name = Path(video_path).stem

    subtitles_dir = Path("subtitles")
    output_dir = Path("output")
    subtitles_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    try:
        # Step 1: Generate SRT
        print("\nStep 1: Generating SRT file...")
        handler = TranscriptionHandler()
        srt_path = handler.transcribe_video(video_path)
        print(f"SRT file saved to: {srt_path}")
        
        # Step 2: Convert SRT to ASS
        ass_path = subtitles_dir / f"{video_name}.ass"
        run_command([
            "ffmpeg",
            "-y",  # Overwrite if exists
            "-i", str(srt_path),
            str(ass_path)
        ], "Converting SRT to ASS")
        
        # Step 3: Copy ASS to current dir (for relative path)
        print("\nStep 3: Copying ASS file to current directory...")
        temp_ass_path = Path("long.ass")
        if temp_ass_path.exists():
            temp_ass_path.unlink()
        shutil.copy2(ass_path, temp_ass_path)
        print("ASS file copied successfully.")
        
        # Step 4: Burn subtitles (NOTE: no quotes around `ass=` value)
        output_path = output_dir / f"{video_name}_with_subs.mp4"
        run_command([
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(video_path),
            "-vf", f"ass={temp_ass_path}",
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ], "Burning subtitles into video")

        print(f"\n✅ Processing complete! Output video saved to: {output_path}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
    finally:
        # Clean up temporary ASS file
        if Path("long.ass").exists():
            Path("long.ass").unlink()
            print("\n🧹 Temporary files cleaned up")

if __name__ == "__main__":
    main()
