"""
Module for generating YouTube titles using OpenRouter API
"""

import requests
import json
from typing import Optional
from config.api_keys import OPENROUTER_API_KEY

class TitleGenerator:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate_title(self, video_description: str) -> Optional[str]:
        """
        Generate a YouTube title using OpenRouter API
        
        Args:
            video_description (str): Description of the video content
            
        Returns:
            Optional[str]: Generated title or None if generation fails
        """
        try:
            prompt = f"""Generate a short, curious YouTube title for a short video with the following description:
            {video_description}
            
            Requirements:
            - Keep it under 4 words
            - Make it practical and relatable
            - Create curiosity and interest
            - Use numbers or emojis if appropriate
            - Make it click-worthy but not clickbait
            - Focus on the most interesting or surprising part
            
            Examples of good titles:
            - "Why She Said Yes"
            - "The Tall Couple Story"
            - "6 Years Later..."
            - "College Love Secrets"
            - "What Happened Next?"
            
            Return only the title, no additional text."""

            payload = {
                "model": "mistralai/mistral-7b-instruct",  # Using a free model
                "messages": [
                    {"role": "system", "content": "You are a YouTube title expert who creates short, engaging titles."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 50
            }

            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            title = result['choices'][0]['message']['content'].strip()
            
            return title

        except Exception as e:
            print(f"Error generating title: {str(e)}")
            return None

# Example usage
if __name__ == "__main__":
    generator = TitleGenerator()
    test_description = "A short clip showing a cat playing with a ball of yarn"
    title = generator.generate_title(test_description)
    print(f"Generated title: {title}") 