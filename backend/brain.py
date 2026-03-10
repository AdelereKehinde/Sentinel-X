import os
from pathlib import Path

import requests
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / "backend" / ".env")

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

try:
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "900"))
except ValueError:
    MAX_TOKENS = 900

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """
You are Sentinel Prime, a desktop AI voice assistant.
Rules:
- Reply in a natural human way, not robotic.
- Give moderate detail by default: around 5-8 sentences.
- Keep answers practical, clear, and helpful.
- Avoid long disclaimers and avoid sounding like generic AI text.
- If asked your name, say your name is Sentinel.
"""


def ask_brain(user_input: str) -> str:
    if not API_KEY:
        raise RuntimeError("Missing OPENROUTER_API_KEY in environment.")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7,
        "top_p": 0.9,
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=35)
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to reach OpenRouter: {exc}") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"OpenRouter returned non-JSON response (status {response.status_code})."
        ) from exc

    if response.status_code >= 400:
        message = result.get("error", {}).get("message") or result.get("message") or result
        raise RuntimeError(f"OpenRouter request failed (status {response.status_code}): {message}")

    choices = result.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenRouter response missing choices: {result}")

    text = choices[0].get("message", {}).get("content", "").strip()
    if not text:
        raise RuntimeError("OpenRouter response missing message content.")

    return text
