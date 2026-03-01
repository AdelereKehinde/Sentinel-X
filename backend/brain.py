import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

SYSTEM_PROMPT = """
You are Sentinel Prime, a desktop AI robot assistant.
You control allowed apps, remember users, and execute safe system tasks.
Respond briefly and clearly like a robot assistant.
"""


def ask_brain(user_input: str) -> str:
    if not API_KEY:
        raise RuntimeError("Missing OPENROUTER_API_KEY in environment.")
    if not MODEL:
        raise RuntimeError("Missing MODEL in environment.")

    data = {
        "model": "openai/gpt-5.2",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=HEADERS, json=data, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to reach brain provider: {exc}") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Brain provider returned non-JSON response (status {response.status_code})."
        ) from exc

    if response.status_code >= 400:
        error_message = result.get("error", {}).get("message") or result.get("message")
        raise RuntimeError(
            f"Brain provider request failed (status {response.status_code}): {error_message or 'Unknown error'}"
        )

    choices = result.get("choices")
    if not choices:
        error_message = result.get("error", {}).get("message") or result.get("message")
        raise RuntimeError(
            f"Brain provider response missing choices: {error_message or result}"
        )

    content = choices[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("Brain provider response missing message content.")

    return content
