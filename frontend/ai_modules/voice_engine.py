import os
import re
import threading
import time
from queue import Queue
from typing import Callable, Optional

import pyttsx3
import requests
import speech_recognition as sr

from ai_modules.memory_engine import memory
from ai_modules.system_control import execute_command

BACKEND_URL = "http://127.0.0.1:8000/brain"
AUTONOMOUS_HEARING = True

_speaking_callback: Optional[Callable[[bool], None]] = None
_ui_reply_callback: Optional[Callable[[str], None]] = None

speech_queue: Queue = Queue()

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 300
recognizer.pause_threshold = 0.7
recognizer.non_speaking_duration = 0.4

engine = pyttsx3.init()
engine.setProperty("rate", 175)
engine.setProperty("volume", 1.0)

voices = engine.getProperty("voices")
if voices:
    engine.setProperty("voice", voices[0].id)

INTRODUCED = False
LAST_RECOGNITION_ERROR_ANNOUNCE = 0.0


def set_speaking_callback(callback: Callable[[bool], None]):
    global _speaking_callback
    _speaking_callback = callback


def set_ui_reply_callback(callback: Callable[[str], None]):
    global _ui_reply_callback
    _ui_reply_callback = callback


def _notify_speaking(state: bool):
    if _speaking_callback:
        try:
            _speaking_callback(state)
        except Exception:
            pass


def _speech_worker():
    while True:
        text = speech_queue.get()
        if text is None:
            continue

        try:
            _notify_speaking(True)
            engine.stop()
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            print("TTS error:", exc)
        finally:
            _notify_speaking(False)
            speech_queue.task_done()


threading.Thread(target=_speech_worker, daemon=True).start()


def speak(text: str):
    if not text:
        return

    clean = str(text).strip()
    if not clean:
        return

    # Send to UI immediately
    if _ui_reply_callback:
        try:
            _ui_reply_callback(clean)
        except Exception:
            pass

    # Queue for TTS
    speech_queue.put(clean)

    max_len = 240
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", clean) if p.strip()]
    if not parts:
        parts = [clean]
    for part in parts:
        if len(part) <= max_len:
            speech_queue.put(part)
            continue
        for i in range(0, len(part), max_len):
            speech_queue.put(part[i : i + max_len].strip())


def _extract_name(text: str) -> Optional[str]:
    lower = text.lower().strip()
    patterns = [
        r"my name is ([a-zA-Z][a-zA-Z\-']*)",
        r"i am ([a-zA-Z][a-zA-Z\-']*)",
        r"i'm ([a-zA-Z][a-zA-Z\-']*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            raw = match.group(1).strip()
            return raw[:1].upper() + raw[1:].lower()
    return None


def _summarize_logs(limit: int = 8) -> str:
    logs = memory.get_recent_logs(limit=limit)
    if not logs:
        return "I do not have logs yet."
    parts = [item.get("event", "") for item in logs if item.get("event")]
    # Avoid reading every low-value technical noise entry aloud.
    parts = [p for p in parts if "Voice loop error" not in p]
    if not parts:
        return "Recent logs are mostly system noise. Ask me to read all logs if you want everything."
    return "Recent logs: " + " | ".join(parts)


def _summarize_conversation(limit: int = 5) -> str:
    rows = memory.get_recent_conversations("user", limit=limit)
    if not rows:
        return "We have no saved conversation yet."
    chunks = []
    for row in rows:
        chunks.append(f"You said {row.get('user', '')}. I said {row.get('sentinel', '')}.")
    return " ".join(chunks)


def _ask_backend(command: str) -> str:
    try:
        response = requests.post(
            BACKEND_URL,
            json={"input_text": command},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("response", "I do not have a response yet.")
    except Exception as exc:
        return f"I could not reach my brain right now: {exc}"


def process_command(command: str):
    text = (command or "").strip()
    if not text:
        return None

    lowered = text.lower()
    memory.log_event(f"User: {text}")

    try:
        from ai_modules.idle_thoughts import idle_engine

        idle_engine.update_activity()
    except Exception:
        pass

    if "what is your name" in lowered or "who are you" in lowered:
        reply = "My name is Sentinel."
        memory.remember_conversation("user", text, reply)
        speak(reply)
        return reply

    if "what is my name" in lowered or "who am i" in lowered:
        current_user = memory.get_current_user()
        if current_user:
            reply = f"Your name is {current_user}."
        else:
            reply = "I do not know your name yet. Tell me by saying my name is..."
        memory.remember_conversation("user", text, reply)
        speak(reply)
        return reply

    detected_name = _extract_name(text)
    if detected_name:
        memory.remember_user(detected_name)
        reply = f"Welcome, {detected_name}."
        memory.remember_conversation("user", text, reply)
        speak(reply)
        return reply

    if any(
        key in lowered
        for key in [
            "read logs",
            "say logs",
            "speak logs",
            "show logs",
            "read the logs",
            "say the logs",
            "tell me the logs",
        ]
    ):
        log_limit = 30 if "all" in lowered else 8
        reply = _summarize_logs(limit=log_limit)
        memory.remember_conversation("user", text, reply)
        speak(reply)
        return reply

    if any(
        key in lowered
        for key in [
            "read conversation",
            "say conversation",
            "our conversation",
            "what did we talk about",
            "read our conversation",
            "say our conversation",
            "tell me our conversation",
        ]
    ):
        conv_limit = 12 if "all" in lowered else 5
        reply = _summarize_conversation(limit=conv_limit)
        memory.remember_conversation("user", text, reply)
        speak(reply)
        return reply

    system_response = execute_command(text)
    if system_response:
        memory.remember_conversation("user", text, system_response)
        speak(system_response)
        return system_response

    reply = _ask_backend(text)
    memory.remember_conversation("user", text, reply)
    speak(reply)
    return reply


def _recognize_audio(audio) -> Optional[str]:
    global LAST_RECOGNITION_ERROR_ANNOUNCE

    # Primary recognizer (online)
    try:
        text = recognizer.recognize_google(audio).strip()
        if text:
            return text.lower()
    except sr.RequestError as exc:
        memory.log_event(f"Speech service error: {exc}")
        now = time.time()
        if now - LAST_RECOGNITION_ERROR_ANNOUNCE > 45:
            speak("I cannot reach online speech recognition. I will try offline mode.")
            LAST_RECOGNITION_ERROR_ANNOUNCE = now
    except sr.UnknownValueError:
        return None
    except Exception as exc:
        memory.log_event(f"Speech recognition error: {exc}")

    # Offline fallback (requires pocketsphinx installed)
    try:
        offline_text = recognizer.recognize_sphinx(audio).strip()
        if offline_text:
            return offline_text.lower()
    except Exception as exc:
        memory.log_event(f"Offline speech unavailable: {exc}")

    return None


def listen(timeout: int = 5, phrase_time_limit: int = 8):
    mic_index = os.getenv("MIC_INDEX")
    device_index = int(mic_index) if mic_index and mic_index.isdigit() else None

    try:
        with sr.Microphone(device_index=device_index) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )
        return _recognize_audio(audio)
    except sr.WaitTimeoutError:
        return None
    except sr.UnknownValueError:
        return None
    except Exception as exc:
        memory.log_event(f"Listen error: {exc}")
        return None


def listen_loop(command_callback=None):
    global INTRODUCED

    mic_index = os.getenv("MIC_INDEX")
    device_index = int(mic_index) if mic_index and mic_index.isdigit() else None

    with sr.Microphone(device_index=device_index) as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.0)

        if not INTRODUCED:
            speak("Hello, my name is Sentinel. What is your name?")
            INTRODUCED = True

        while True:
            try:
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=8)
                text = _recognize_audio(audio)
                if text is None:
                    continue
                if len(text) < 2:
                    continue

                if AUTONOMOUS_HEARING and command_callback:
                    command_callback(text)
                else:
                    process_command(text)
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except Exception as exc:
                memory.log_event(f"Voice loop error: {exc}")
                continue
