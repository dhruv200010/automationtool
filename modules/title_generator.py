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

    def extract_title_and_hashtags(self, text: str) -> Optional[Tuple[str, list, str]]:
        """Extract title, hashtags, and description from various response formats"""
        try:
            # Initialize variables
            title = ""
            hashtags = []
            description = ""
            
            # Split by newlines and remove empty lines
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Process each line
            for line in lines:
                # Extract title
                if line.lower().startswith('title:'):
                    title = line[6:].strip()
                    title = re.sub(r'\{(\w+)\}', r'\1', title)  # Remove curly braces
                    title = title.strip('"')  # Remove any surrounding quotes
                    continue
                
                # Extract hashtags
                if line.lower().startswith('hashtags:'):
                    tags = line[9:].strip()
                    found_tags = re.findall(r'#\{?(\w+)\}?', tags)
                    hashtags.extend([f"#{tag}" for tag in found_tags])
                    continue
                
                # Extract description
                if line.lower().startswith('description:'):
                    description = line[12:].strip()
                    description = description.strip('"')  # Remove any surrounding quotes
                    continue
            
            # If no title found, use the first line
            if not title and lines:
                title = lines[0]
                title = re.sub(r'\{(\w+)\}', r'\1', title)
                title = title.strip('"')  # Remove any surrounding quotes
            
            # If no hashtags found, extract from all lines
            if not hashtags:
                for line in lines:
                    found_tags = re.findall(r'#\{?(\w+)\}?', line)
                    hashtags.extend([f"#{tag}" for tag in found_tags])
            
            # Remove duplicates and limit to 4 tags
            hashtags = list(dict.fromkeys(hashtags))[:4]
            
            # If no hashtags found, add some default ones
            if not hashtags:
                hashtags = ["#shorts", "#love"]
            
            # If no description found, create a default one
            if not description:
                description = f"A heartwarming moment captured in this short video. {title}"
            
            return title, hashtags, description
        except Exception as e:
            print(f"Error extracting title, hashtags, and description: {str(e)}")
            return None

    def generate_title_and_hashtags(self, video_description: str) -> Optional[Tuple[str, list, str]]:
        """
        Generate a YouTube title, hashtags, and description using OpenRouter API
        
        Args:
            video_description (str): Description of the video content
            
        Returns:
            Optional[Tuple[str, list, str]]: Generated title, hashtags, and description, or None if generation fails
        """
        try:
            if not video_description or video_description.isspace():
                print("Error: Empty video description provided")
                return None

            print(f"\nGenerating title for content: {video_description[:100]}...")

            prompt = f"""Generate a YouTube Shorts title, hashtags, and SEO-optimized description for a video with the following content:
            {video_description}
            
            Rules for Generation:
            🔠 Title:
            - Max 4 words
            - Use simple, easy-to-understand English
            - Avoid complex vocab or long phrases
            - MUST include at least 2 hashtags inside the title (at the end)
            - Hashtags should be relevant, popular, and based on video content
            - Optionally include #shorts hashtag when appropriate for the content
            - NEVER use personal names in titles or hashtags
            - Focus on themes, locations, emotions, and activities instead

            Example formats:
            "Ranch Love Story #texas #love #shorts"
            "Funny First Date #nyc #love"
            "6 Years Married #marriage #love #shorts"

            🏷️ Hashtags:
            - Should not duplicate the ones in the title
            - Up to 3-4 hashtags only
            - Popular and relevant to the context (e.g., #couplegoals, #romance, #citylife, #marriedlife)
            - Consider adding #shorts if not in title and content is short-form
            - NEVER use personal names as hashtags
            - Focus on themes, locations, emotions, and activities instead

            🧾 Description:
            - Write a 2-3 sentence engaging description that explains what's happening in the video
            - Include key details like:
              * What the couple is doing
              * Where they are (if location is mentioned)
              * Their relationship status or context
              * Any emotional moments or reactions
              * Any interesting backstory or context
            - Use natural, conversational language
            - Include relevant keywords for better SEO
            - Keep it under 150 characters
            - Make it engaging and click-worthy
            - Avoid using personal names in the description

            Example Description:
            "A couple married for 6 years shares their favorite things about each other and the story of how they found their dog in Texas. A sweet and heartfelt moment in NYC that shows the beauty of long-term love."

            Return the title, hashtags, and description in this format:
            Title: [Your title here]
            Hashtags: [Your hashtags here]
            Description: [Your description here]"""

            payload = {
                "model": "mistralai/mistral-7b-instruct",
                "messages": [
                    {"role": "system", "content": "You are a YouTube Shorts title and hashtag expert who creates engaging, romantic content with SEO-optimized descriptions."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 200
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
            
            # Extract title, hashtags, and description from the response
            result = self.extract_title_and_hashtags(output)
            if result:
                title, hashtags, description = result
                print(f"Extracted title: {title}")
                print(f"Extracted hashtags: {' '.join(hashtags)}")
                print(f"Extracted description: {description}")
                return title, hashtags, description
            
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
        title, hashtags, description = result
        print(f"Generated title: {title}")
        print(f"Generated hashtags: {' '.join(hashtags)}")
        print(f"Generated description: {description}") 