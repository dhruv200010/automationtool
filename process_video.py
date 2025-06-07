import os
import sys
import shutil
from pathlib import Path
import subprocess
from modules.transcription import TranscriptionHandler

def run_command(cmd, description):
    """Run a command and print its output"""
    print(f"\n{description}...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print("Error Output:")
        print(result.stderr)
        raise Exception(f"Command failed: {' '.join(cmd)}")
    return result

def create_karaoke_style():
    """Create the style section for karaoke subtitles"""
    return """
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat Black,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,200,1
Style: Highlight1,Montserrat Black,16,&H00F767C8,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,200,1
Style: Highlight2,Montserrat Black,16,&H00FB12C0,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,200,1
Style: Highlight3,Montser Black,16,&H0000B557,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,200,1
"""

def create_karaoke_dialogue(words, start_time, end_time):
    """Create dialogue entries for karaoke effect"""
    if not words:
        return ""
    
    # Calculate time per word
    total_duration = end_time - start_time
    time_per_word = total_duration / len(words)
    
    # Colors for highlighting in the exact sequence requested
    highlight_colors = ["&HC867F7&", "&H12C0FB&", "&HB55700&"]
    
    dialogue_entries = []
    # Use a unique layer number for each line to ensure proper replacement
    layer = 1
    
    for i, word in enumerate(words):
        word_start = start_time + (i * time_per_word)
        word_end = word_start + time_per_word
        
        # Create the line with the current word highlighted
        line = []
        for j, w in enumerate(words):
            if j == i:
                # Current word gets highlighted with proper ASS override syntax
                color_index = i % 3
                line.append(f"{{\\c{highlight_colors[color_index]}}}{w}{{\\c&H00FFFFFF&}}")
            else:
                # Other words stay white
                line.append(w)
        
        # Format time as h:mm:ss.cc
        start_str = f"{int(word_start//3600):01d}:{int((word_start%3600)//60):02d}:{int(word_start%60):02d}.{int((word_start%1)*100):02d}"
        end_str = f"{int(word_end//3600):01d}:{int((word_end%3600)//60):02d}:{int(word_end%60):02d}.{int((word_end%1)*100):02d}"
        
        dialogue_entry = f"Dialogue: {layer},{start_str},{end_str},Default,,0,0,0,,{' '.join(line)}"
        dialogue_entries.append(dialogue_entry)
    
    return "\n".join(dialogue_entries)

def modify_ass_file(ass_path):
    """Modify ASS file to create karaoke-style subtitles"""
    with open(ass_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add the style section
    style_section = create_karaoke_style()
    
    # Extract the Events section
    events_section = ""
    if "[Events]" in content:
        events_start = content.find("[Events]")
        events_end = content.find("\n\n", events_start)
        if events_end == -1:
            events_end = len(content)
        events_section = content[events_start:events_end]
    
    # Create new dialogue entries
    new_dialogues = []
    line_counter = 1  # Counter for unique layers per line
    
    for line in content.split("\n"):
        if line.startswith("Dialogue:"):
            # Parse the dialogue line
            parts = line.split(",", 9)
            if len(parts) >= 10:
                start_time = parts[1]
                end_time = parts[2]
                text = parts[9]
                
                # Split text into words
                words = text.split()
                
                # Create karaoke-style dialogue entries with unique layer
                new_dialogues.append(create_karaoke_dialogue(words, 
                    float(start_time.split(":")[0])*3600 + 
                    float(start_time.split(":")[1])*60 + 
                    float(start_time.split(":")[2]),
                    float(end_time.split(":")[0])*3600 + 
                    float(end_time.split(":")[1])*60 + 
                    float(end_time.split(":")[2])))
                line_counter += 1
    
    # Combine all sections
    new_content = content.split("[V4+ Styles]")[0] + style_section + "\n"
    new_content += events_section + "\n"
    new_content += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    new_content += "\n".join(new_dialogues)
    
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

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
        
        # Step 4: Modify ASS file to create karaoke-style subtitles
        print("\nStep 4: Modifying ASS file to create karaoke-style subtitles...")
        modify_ass_file(temp_ass_path)
        print("ASS file modified successfully.")
        
        # Step 5: Burn subtitles
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
