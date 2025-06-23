import os
import sys
import json
import shutil
from pathlib import Path
import subprocess

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

from modules.transcription import TranscriptionHandler

def run_command(command, step_name):
    """Run a command and print its output"""
    print(f"\n{step_name}...")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        print(f"Command output: {e.stdout}")
        print(f"Command error: {e.stderr}")
        return False

def create_karaoke_style():
    """Create the style section for karaoke subtitles"""
    return """
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat Black,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,170,1
Style: Highlight1,Montserrat Black,16,&H00C867F7,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,170,1
Style: Highlight2,Montserrat Black,16,&H0012C0FB,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,170,1
Style: Highlight3,Montser Black,16,&H00B55700,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,8,10,10,170,1
"""

def create_karaoke_dialogue(words, start_time, end_time, start_word_index=0):
    """Create dialogue entries for karaoke effect"""
    if not words:
        return ""
    
    # Colors for highlighting in the exact sequence requested
    highlight_colors = ["&H00C867F7&", "&H0012C0FB&", "&H00B55700&"]
    
    # Break words into chunks of 4 words each
    chunk_size = 4
    word_chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    
    # Calculate time per chunk
    total_duration = end_time - start_time
    time_per_chunk = total_duration / len(word_chunks) if word_chunks else 0
    
    dialogue_entries = []
    layer = 1  # Keep layer consistent for these entries
    
    for chunk_index, chunk in enumerate(word_chunks):
        if not chunk:
            continue

        # Calculate timing for this chunk
        chunk_start = start_time + (chunk_index * time_per_chunk)
        chunk_end = chunk_start + time_per_chunk
        
        # Calculate time per word within this chunk
        chunk_duration = chunk_end - chunk_start
        time_per_word = chunk_duration / len(chunk) if chunk else 0
        
        mid = len(chunk) // 2
        
        # Iterate through each word in the chunk to create a dialogue line where it's highlighted
        for i, word_to_highlight in enumerate(chunk):
            word_start = chunk_start + (i * time_per_word)
            word_end = word_start + time_per_word
            
            # Build the complete line text for this specific highlight
            line_parts = []
            for j, w in enumerate(chunk):
                # Fix apostrophe capitalization
                if "'" in w:
                    parts = w.split("'")
                    w = parts[0] + "'" + parts[1].lower()

                if i == j:  # The word to highlight
                    color_index = (start_word_index + (chunk_index * chunk_size) + j) % 3
                    line_parts.append(f"{{\\c{highlight_colors[color_index]}\\1a&H00&}}{w}{{\\c&H00FFFFFF&\\1a&H00&}}")
                else:  # Other words
                    line_parts.append(f"{{\\1a&H00&}}{w}")
                
                # Add a line break if the chunk is being split and we're at the midpoint
                if len(chunk) > 1 and mid > 0 and j == mid - 1:
                    line_parts.append("\\N")

            # Join parts and clean up potential space around the line break
            line_text = " ".join(line_parts).replace(" \\N ", "\\N")
            
            # Format time as h:mm:ss.cc
            start_str = f"{int(word_start//3600):01d}:{int((word_start%3600)//60):02d}:{int(word_start%60):02d}.{int((word_start%1)*100):02d}"
            end_str = f"{int(word_end//3600):01d}:{int((word_end%3600)//60):02d}:{int(word_end%60):02d}.{int((word_end%1)*100):02d}"
            
            dialogue_entry = f"Dialogue: {layer},{start_str},{end_str},Default,,0,0,0,,{line_text}"
            dialogue_entries.append(dialogue_entry)
            
    return "\n".join(dialogue_entries)

def modify_ass_file(ass_path):
    """Modify ASS file to create karaoke-style subtitles"""
    with open(ass_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add the style section
    style_section = create_karaoke_style()
    
    # Extract the Events section header
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
    global_word_index = 0  # Global counter for continuous word coloring
    
    # Only keep the non-Dialogue lines
    non_dialogue_lines = [
        line for line in content.split("\n")
        if not line.startswith("Dialogue:")
    ]
    
    # Process the original dialogue lines to create karaoke versions
    for line in content.split("\n"):
        if line.startswith("Dialogue:"):
            # Parse the dialogue line
            parts = line.split(",", 9)
            if len(parts) >= 10:
                start_time = parts[1]
                end_time = parts[2]
                text = parts[9]
                
                # Split text into words, preserving \N
                words = []
                for part in text.split("\\N"):
                    words.extend(part.split())
                    if "\\N" in text:
                        words.append("\\N")
                
                # Remove empty strings and trailing \N
                words = [w for w in words if w and w != "\\N"]
                
                # Only process if we have words
                if words:
                    # Create karaoke-style dialogue entries with unique layer
                    dialogue_entries = create_karaoke_dialogue(words, 
                        float(start_time.split(":")[0])*3600 + 
                        float(start_time.split(":")[1])*60 + 
                        float(start_time.split(":")[2]),
                        float(end_time.split(":")[0])*3600 + 
                        float(end_time.split(":")[1])*60 + 
                        float(end_time.split(":")[2]),
                        global_word_index)
                    
                    if dialogue_entries:  # Only add if we have entries
                        new_dialogues.append(dialogue_entries)
                        global_word_index += len(words)  # Increment word index by number of words
                        line_counter += 1
    
    # Combine all sections, excluding original dialogue lines
    new_content = "\n".join(non_dialogue_lines).split("[V4+ Styles]")[0] + style_section + "\n"
    new_content += "[Events]\n"
    new_content += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    new_content += "\n".join(new_dialogues)
    
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

def main():
    if len(sys.argv) != 2:
        print("Usage: python src/add_subtitles.py <video_path>")
        print("Example: python src/add_subtitles.py C:/Users/sendt/Downloads/long.MOV")
        sys.exit(1)
    
    video_path = Path(sys.argv[1])
    video_name = video_path.stem

    # Load and normalize output folder from config
    config_path = project_root / "config" / "master_config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        output_root = Path(config['output_folder']).expanduser().resolve()
    
    subtitles_dir = output_root / "subtitles"
    output_root.mkdir(parents=True, exist_ok=True)
    subtitles_dir.mkdir(parents=True, exist_ok=True)

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
        output_path = output_root / f"{video_name}_with_subs.mp4"
        run_command([
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(video_path),
            "-vf", f"ass={temp_ass_path},format=yuv420p,colorspace=all=bt709:iall=bt709:fast=1",
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
