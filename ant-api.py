import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variables
api_key = os.getenv("ANTHROPIC_API_KEY")

# API endpoint
url = "https://api.anthropic.com/v1/messages"

# Headers
headers = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
}

# User message
user_message = "Tell me a short interesting fact about space."

# Request body
data = {
    "model": "claude-3-5-haiku-20241022",
    "max_tokens": 1000,
    "messages": [
        {"role": "user", "content": user_message}
    ]
}

# Make the API request
response = requests.post(url, headers=headers, json=data)

# Check if the request was successful
if response.status_code == 200:
    # Parse the JSON response
    result = response.json()
    
    # Print the message content from Claude
    print("\nClaude's response:")
    print(result['content'][0]['text'])
else:
    print(f"Error: {response.status_code}")
    print(response.text)