import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env file")

response = requests.post(
  url="https://openrouter.ai/api/v1/chat/completions",
  headers={
    "Authorization": f"Bearer {API_KEY}",
    "HTTP-Referer": "https://localhost",
    "X-OpenRouter-Title": "Sentinel",
    "Content-Type": "application/json",
  },
  json={
    "model": "openai/gpt-4-turbo",
    "messages": [
      {
        "role": "user",
        "content": "What is the meaning of life?"
      }
    ]
  }
)

print(response.json())
