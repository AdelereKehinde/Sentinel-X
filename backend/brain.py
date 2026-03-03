import os
from pathlib import Path

import requests
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / "frontend" / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-04-17")

try:
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "700"))
except ValueError:
    MAX_TOKENS = 700

SYSTEM_PROMPT = """
You are Sentinel Prime, a desktop AI voice assistant.
Rules:
- Speak like a natural person, not a formal AI.
- Give useful detail by default: normally 3-6 short sentences.
- Avoid jargon and long disclaimers.
- Be practical and direct.
- If asked your name, say you are Sentinel.
- Do not just echo the user's words. Answer the actual question clearly.
"""


def ask_brain(user_input: str) -> str:
    if not API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY in environment.")

    url = (
        f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent"
        f"?key={API_KEY}"
    )

    # IMPORTANT: For Gemini 2.5, system prompt goes in the user message content
    # or use a separate approach
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{SYSTEM_PROMPT}\n\nUser query: {user_input}"}
                ],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": MAX_TOKENS,
            "temperature": 0.7,
            "topP": 0.9,
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to reach Gemini: {exc}") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Gemini returned non-JSON response (status {response.status_code})."
        ) from exc

    if response.status_code >= 400:
        message = result.get("error", {}).get("message") or result
        raise RuntimeError(f"Gemini request failed (status {response.status_code}): {message}")

    candidates = result.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini response missing candidates: {result}")

    # Extract text from response
    try:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"Failed to parse response: {e}\nResponse: {result}")
    
    return ""
