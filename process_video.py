import os
import sys
import shutil
from pathlib import Path
import subprocess
from modules.transcription import TranscriptionHandler

def run_command(cmd, description):
    """Run a command and print its output"""
    print(f"\n{description}...")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    
    for line in process.stdout:
        print(line.strip())
    
    process.wait()
    if process.returncode != 0:
        raise Exception(f"Command failed with return code {process.returncode}")

def modify_ass_file(ass_path):
    """Modify ASS file to center subtitles vertically"""
    with open(ass_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add or modify the Style section to center subtitles vertically
    style_section = """
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,14,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,8,10,10,200,1
"""
    
    # If the file already has a Style section, replace it
    if "[V4+ Styles]" in content:
        parts = content.split("[V4+ Styles]")
        content = parts[0] + style_section + parts[1].split("\n\n", 1)[1]
    else:
        # Add the Style section after the Script Info section
        parts = content.split("[Script Info]")
        content = parts[0] + "[Script Info]" + parts[1].split("\n\n", 1)[0] + style_section + parts[1].split("\n\n", 1)[1]
    
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(content)

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
        
        # Step 4: Modify ASS file to center subtitles
        print("\nStep 4: Modifying ASS file to center subtitles...")
        modify_ass_file(temp_ass_path)
        print("ASS file modified successfully.")
        
        # Step 5: Burn subtitles (NOTE: no quotes around `ass=` value)
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

        print(f"\nProcessing complete! Output video saved to: {output_path}")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        sys.exit(1)
    finally:
        # Clean up temporary ASS file
        if Path("long.ass").exists():
            Path("long.ass").unlink()
            print("\nTemporary files cleaned up")

if __name__ == "__main__":
    main()
