import os
import json
import requests
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

class AITransliterator:
    """
    AI-based Hindi transliterator using OpenRouter API.
    Converts Hindi Devanagari script to natural Roman script.
    """
    
    def __init__(self):
        """Initialize the AI transliterator."""
        # Load environment variables
        project_root = Path(__file__).parent.parent
        load_dotenv(project_root / "config" / "config.env")
        
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def transliterate_hindi_to_roman(self, hindi_text: str) -> str:
        """
        Convert Hindi text from Devanagari script to natural Roman script using AI.
        
        Args:
            hindi_text (str): Hindi text in Devanagari script
            
        Returns:
            str: Hindi text transliterated to natural Roman script
        """
        if not hindi_text or not hindi_text.strip():
            return hindi_text
        
        try:
            # Create the prompt for transliteration
            prompt = f"""Transliterate this Hindi text to Roman script (casual style like WhatsApp):

{hindi_text}

Roman transliteration:"""

            payload = {
                "model": "anthropic/claude-3-haiku",  # Free and fast model
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a Hindi transliteration expert. Convert Hindi Devanagari text to natural Roman script as Hindi speakers would type it casually. Return ONLY the transliterated text, no prefixes or explanations."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 200,
                "temperature": 0.1  # Low temperature for consistent results
            }
            
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            transliterated_text = result['choices'][0]['message']['content'].strip()
            
            # Clean up the response (remove any prefixes or extra text)
            prefixes_to_remove = [
                "Transliterated text:",
                "Roman transliteration:",
                "Transliteration:",
                "Roman script:",
                "Hindi transliteration:"
            ]
            
            for prefix in prefixes_to_remove:
                if transliterated_text.startswith(prefix):
                    transliterated_text = transliterated_text.replace(prefix, "").strip()
            
            # Additional cleaning: remove any lines that start with common prefixes
            lines = transliterated_text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line and not any(line.startswith(prefix) for prefix in prefixes_to_remove):
                    cleaned_lines.append(line)
            
            transliterated_text = ' '.join(cleaned_lines)
            
            return transliterated_text
            
        except Exception as e:
            print(f"Error in AI transliteration: {e}")
            return hindi_text
    
    def transliterate_srt_file(self, srt_path: Path) -> Path:
        """
        Transliterate an SRT file from Hindi Devanagari to natural Roman script using AI.
        
        Args:
            srt_path (Path): Path to the input SRT file
            
        Returns:
            Path: Path to the transliterated SRT file
        """
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_path}")
        
        # Create output path with _ai_roman suffix
        output_path = srt_path.parent / f"{srt_path.stem}_ai_roman.srt"
        
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split content into subtitle blocks
            blocks = content.strip().split('\n\n')
            transliterated_blocks = []
            
            for block in blocks:
                lines = block.split('\n')
                if len(lines) >= 3:
                    # First line is subtitle number
                    number = lines[0]
                    # Second line is timestamp
                    timestamp = lines[1]
                    # Remaining lines are the subtitle text
                    subtitle_text = '\n'.join(lines[2:])
                    
                    # Transliterate the subtitle text using AI
                    transliterated_text = self.transliterate_hindi_to_roman(subtitle_text)
                    
                    # Reconstruct the block
                    transliterated_block = f"{number}\n{timestamp}\n{transliterated_text}"
                    transliterated_blocks.append(transliterated_block)
                else:
                    # Keep blocks that don't follow the expected format
                    transliterated_blocks.append(block)
            
            # Write the transliterated content
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(transliterated_blocks))
            
            print(f"AI transliterated SRT saved to: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error transliterating SRT file: {e}")
            raise
    
    def transliterate_text_segments(self, segments: list) -> list:
        """
        Transliterate text segments from Hindi Devanagari to natural Roman script using AI.
        
        Args:
            segments (list): List of segments with 'text' field
            
        Returns:
            list: List of segments with transliterated text
        """
        transliterated_segments = []
        
        for segment in segments:
            if 'text' in segment:
                transliterated_text = self.transliterate_hindi_to_roman(segment['text'])
                segment_copy = segment.copy()
                segment_copy['text'] = transliterated_text
                transliterated_segments.append(segment_copy)
            else:
                transliterated_segments.append(segment)
        
        return transliterated_segments


def test_ai_transliteration():
    """Test function to verify AI transliteration works correctly."""
    transliterator = AITransliterator()
    
    # Test Hindi text in Devanagari
    test_cases = [
        "अगर",
        "दीदी subscribe के साथ साथ अगर थोड़े से फल भी ले जाती तो अच्छा होता",
        "पर कोई बात नहीं",
        "नहीं",
        "मैं बिल्कुल ठीक हूँ",
        "आपका नाम क्या है?"
    ]
    
    print("Testing AI-based Hindi transliteration...")
    print("="*60)
    
    for i, hindi_text in enumerate(test_cases, 1):
        transliterated = transliterator.transliterate_hindi_to_roman(hindi_text)
        print(f"\nTest {i}:")
        print(f"Original (Devanagari): {hindi_text}")
        print(f"AI Transliterated (Roman): {transliterated}")
    
    print("\n" + "="*60)
    print("AI transliteration test completed!")
    print("="*60)


if __name__ == "__main__":
    test_ai_transliteration() 