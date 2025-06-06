"""
Module for generating YouTube titles and hashtags using OpenRouter API
"""

import requests
import json
import re
from typing import Optional, Tuple
from config.api_keys import OPENROUTER_API_KEY

class TitleGenerator:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def extract_title_and_hashtags(self, text: str) -> Optional[Tuple[str, list]]:
        """Extract title and hashtags from various response formats"""
        try:
            # Remove any quotes around the title and "Title:" prefix
            text = text.strip('"')
            text = re.sub(r'^Title:\s*', '', text, flags=re.IGNORECASE)
            
            # Split by newlines and remove empty lines
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Get the first line as title and clean it
            title = lines[0]
            # Remove curly braces from the title
            title = re.sub(r'\{(\w+)\}', r'\1', title)
            
            # Extract hashtags from all lines
            hashtags = []
            for line in lines:
                # Find all hashtags in the line, including those with curly braces
                found_tags = re.findall(r'#\{?(\w+)\}?', line)
                # Convert to proper hashtag format
                hashtags.extend([f"#{tag}" for tag in found_tags])
            
            # Remove duplicates and limit to 4 tags
            hashtags = list(dict.fromkeys(hashtags))[:4]
            
            # If no hashtags found, add some default ones
            if not hashtags:
                hashtags = ["#shorts", "#love"]
            
            return title, hashtags
        except Exception as e:
            print(f"Error extracting title and hashtags: {str(e)}")
            return None

    def generate_title_and_hashtags(self, video_description: str) -> Optional[Tuple[str, list]]:
        """
        Generate a YouTube title and hashtags using OpenRouter API
        
        Args:
            video_description (str): Description of the video content
            
        Returns:
            Optional[Tuple[str, list]]: Generated title and hashtags, or None if generation fails
        """
        try:
            if not video_description or video_description.isspace():
                print("Error: Empty video description provided")
                return None

            print(f"\nGenerating title for content: {video_description[:100]}...")

            prompt = f"""Generate a YouTube Shorts title and hashtags for a video with the following description:
            {video_description}
            
            Title Requirements:
            - Keep it under 50 characters
            - Romantic, heartwarming, or serendipitous tone
            - Often set in real cities or everyday moments
            - Use emojis sparingly and only when they add flavor (e.g. ❤️, 😃, 💈, 🤿)
            
            Hashtag Requirements:
            - Include 2-4 relevant hashtags
            - Include location hashtag if city is mentioned (#nyc, #london)
            - Include theme hashtags (#love, #romance, #couplegoals, #shorts)
            - Include context hashtags (#sun, #club, #church, etc.)
            
            Examples of good outputs:
            "6 Years of Love in NYC ❤️ #nyc #love #shorts"
            "Coffee Shop Serendipity #london #romance #cafe"
            "Sunset Beach Proposal #miami #love #proposal"
            
            Return the title and hashtags in any format, just make sure to include hashtags."""

            payload = {
                "model": "mistralai/mistral-7b-instruct",
                "messages": [
                    {"role": "system", "content": "You are a YouTube Shorts title and hashtag expert who creates engaging, romantic content."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 100
            }

            print("Sending request to OpenRouter API...")
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            
            if response.status_code != 200:
                print(f"API Error: Status code {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
            response.raise_for_status()
            
            result = response.json()
            if 'choices' not in result or not result['choices']:
                print("Error: No choices in API response")
                print(f"Response: {result}")
                return None
                
            output = result['choices'][0]['message']['content'].strip()
            print(f"API Response: {output}")
            
            # Extract title and hashtags from the response
            result = self.extract_title_and_hashtags(output)
            if result:
                title, hashtags = result
                print(f"Extracted title: {title}")
                print(f"Extracted hashtags: {' '.join(hashtags)}")
                return title, hashtags
            
            return None

        except requests.exceptions.RequestException as e:
            print(f"Network Error: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {str(e)}")
            print(f"Response text: {response.text}")
            return None
        except Exception as e:
            print(f"Unexpected Error: {str(e)}")
            return None

# Example usage
if __name__ == "__main__":
    generator = TitleGenerator()
    test_description = "A couple meets at a bookstore, discovers common favorite poems, and walks around NYC"
    result = generator.generate_title_and_hashtags(test_description)
    if result:
        title, hashtags = result
        print(f"Generated title: {title}")
        print(f"Generated hashtags: {' '.join(hashtags)}") 