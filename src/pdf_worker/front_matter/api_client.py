import os
import requests
import json
import logging
from dotenv import load_dotenv

class AnthropicClient:
    """Client for interacting with Anthropic's Claude API."""
    
    def __init__(self, api_key=None, model="claude-3-5-haiku-20241022"):
        """
        Initialize the Anthropic API client.
        
        Args:
            api_key (str, optional): Anthropic API key. If not provided, will look for ANTHROPIC_API_KEY in env.
            model (str, optional): Model to use. Defaults to claude-3-5-haiku.
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Load environment variables if no API key provided
        if not api_key:
            load_dotenv()
            api_key = os.getenv("ANTHROPIC_API_KEY")
            
        if not api_key:
            self.logger.error("No Anthropic API key provided")
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable or pass to constructor.")
            
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
    def generate_text(self, prompt, max_tokens=1000, temperature=0.7):
        """
        Generate text using Anthropic's Claude API.
        
        Args:
            prompt (str): The prompt to send to Claude
            max_tokens (int, optional): Maximum number of tokens to generate. Defaults to 1000.
            temperature (float, optional): Controls randomness (0.0 to 1.0). Defaults to 0.7.
            
        Returns:
            str: Generated text response
        """
        try:
            data = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            self.logger.info(f"Sending prompt to Anthropic API using model {self.model}")
            response = requests.post(self.api_url, headers=self.headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                return result['content'][0]['text']
            else:
                self.logger.error(f"API request failed with status code {response.status_code}: {response.text}")
                raise Exception(f"API request failed: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Error generating text: {str(e)}")
            raise