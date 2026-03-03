import os
import re
import threading
import time
import importlib.util
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
_currently_speaking = False


speech_queue: Queue = Queue()

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = int(os.getenv("SR_ENERGY_THRESHOLD", "140"))
recognizer.pause_threshold = float(os.getenv("SR_PAUSE_THRESHOLD", "0.8"))
recognizer.non_speaking_duration = float(os.getenv("SR_NON_SPEAKING_DURATION", "0.35"))

engine = pyttsx3.init()
engine.setProperty("rate", int(os.getenv("VOICE_RATE", "155")))
engine.setProperty("volume", 1.0)

voices = engine.getProperty("voices")
if voices:
    preferred = os.getenv("VOICE_NAME", "").strip().lower()
    chosen = None
    if preferred:
        for v in voices:
            if preferred in (v.name or "").lower():
                chosen = v
                break
    if chosen is None:
        # Prefer clearer conversational Windows voices when available.
        preferred_keywords = ["zira", "david", "hazel", "aria", "jenny", "guy"]
        for key in preferred_keywords:
            for v in voices:
                name = (v.name or "").lower()
                if key in name:
                    chosen = v
                    break
            if chosen is not None:
                break
    if chosen is None:
        chosen = voices[0]
    engine.setProperty("voice", chosen.id)

INTRODUCED = False
LAST_RECOGNITION_ERROR_ANNOUNCE = 0.0
OFFLINE_SPEECH_AVAILABLE = importlib.util.find_spec("pocketsphinx") is not None
OFFLINE_SPEECH_WARNED = False

AVAILABLE_VOICES = engine.getProperty("voices")

def list_voices():
    return [(i, v.name) for i, v in enumerate(AVAILABLE_VOICES)]

def set_voice(index: int):
    if 0 <= index < len(AVAILABLE_VOICES):
        engine.setProperty("voice", AVAILABLE_VOICES[index].id)

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
    global _currently_speaking
    while True:
        text = speech_queue.get()
        if text is None:
            continue

        try:
            _currently_speaking = True
            _notify_speaking(True)
            engine.stop()
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            print("TTS error:", exc)
        finally:
            _notify_speaking(False)
            _currently_speaking = False
            speech_queue.task_done()


threading.Thread(target=_speech_worker, daemon=True).start()


def speak(text: str, interrupt: bool = True):
    if not text:
        return

    clean = str(text).strip()
    if not clean:
        return

    if _ui_reply_callback:
        try:
            _ui_reply_callback(clean)
        except Exception:
            pass

    if interrupt:
        try:
            engine.stop()
            while not speech_queue.empty():
                speech_queue.get_nowait()
                speech_queue.task_done()
        except Exception:
            pass

    # Add gentle pacing so replies sound conversational, not rushed.
    clean = (
        clean.replace("...", ". ")
        .replace(" - ", ", ")
        .replace(";", ". ")
    )

    max_len = 220
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", clean) if p.strip()]
    if not parts:
        parts = [clean]

    for part in parts:
        if len(part) <= max_len:
            speech_queue.put(part)
        else:
            for i in range(0, len(part), max_len):
                speech_queue.put(part[i:i+max_len].strip())

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
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("response", "I do not have a response yet.")
    except Exception as exc:
        return f"I could not reach my brain right now: {exc}"


def _pick_microphone_index() -> Optional[int]:
    # User override wins if valid.
    mic_index = os.getenv("MIC_INDEX")
    if mic_index and mic_index.isdigit():
        return int(mic_index)

    try:
        names = sr.Microphone.list_microphone_names()
    except Exception:
        return None

    if not names:
        return None

    # Prefer real mic capture devices, avoid mapper/stereo mix/output.
    preferred = []
    for i, raw_name in enumerate(names):
        name = (raw_name or "").lower()
        score = 0
        if "microphone" in name or "mic" in name:
            score += 5
        if "realtek" in name:
            score += 2
        if "mapper" in name:
            score -= 3
        if "stereo mix" in name or "output" in name or "speaker" in name:
            score -= 5
        preferred.append((score, i))

    preferred.sort(reverse=True)
    best_score, best_index = preferred[0]
    return best_index if best_score > -1 else None


def _microphone_candidates() -> list[Optional[int]]:
    mic_index = os.getenv("MIC_INDEX")
    if mic_index and mic_index.isdigit():
        return [int(mic_index)]

    try:
        names = sr.Microphone.list_microphone_names()
    except Exception:
        return [None]

    scored: list[tuple[int, int]] = []
    for i, raw_name in enumerate(names):
        name = (raw_name or "").lower()
        score = 0
        if "microphone" in name or "mic" in name:
            score += 6
        if "realtek" in name:
            score += 2
        if "usb" in name:
            score += 2
        if "stereo mix" in name:
            score -= 8
        if "output" in name or "speaker" in name:
            score -= 6
        if "mapper" in name:
            score -= 3
        scored.append((score, i))

    scored.sort(reverse=True)
    candidates = [i for score, i in scored if score >= 0]
    if None not in candidates:
        candidates.append(None)
    return candidates[:6]


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
    global LAST_RECOGNITION_ERROR_ANNOUNCE, OFFLINE_SPEECH_WARNED

    # Primary recognizer (online)
    try:
        text = recognizer.recognize_google(audio).strip()
        if text:
            return text.lower()
    except sr.RequestError as exc:
        memory.log_event(f"Speech service error: {exc}")
        now = time.time()
        if now - LAST_RECOGNITION_ERROR_ANNOUNCE > 45:
            if OFFLINE_SPEECH_AVAILABLE:
                speak("I cannot reach online speech recognition. I will try offline mode.")
            else:
                speak("I cannot reach online speech recognition. Type your command, or install offline speech support.")
            LAST_RECOGNITION_ERROR_ANNOUNCE = now
    except sr.UnknownValueError:
        return None
    except Exception as exc:
        memory.log_event(f"Speech recognition error: {exc}")

    # Offline fallback (requires pocketsphinx installed)
    if OFFLINE_SPEECH_AVAILABLE:
        try:
            offline_text = recognizer.recognize_sphinx(audio).strip()
            if offline_text:
                return offline_text.lower()
        except Exception as exc:
            memory.log_event(f"Offline speech unavailable: {exc}")
    elif not OFFLINE_SPEECH_WARNED:
        memory.log_event("Offline speech unavailable: pocketsphinx is not installed.")
        OFFLINE_SPEECH_WARNED = True

    return None


def listen(timeout: int = 5, phrase_time_limit: int = 8):
    device_index = _pick_microphone_index()

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

    while True:
        for device_index in _microphone_candidates():
            try:
                mic_names = sr.Microphone.list_microphone_names()
                picked_name = (
                    mic_names[device_index]
                    if device_index is not None and device_index < len(mic_names)
                    else "default"
                )
                memory.log_event(f"Voice input device: {picked_name} (index={device_index})")
            except Exception:
                memory.log_event("Voice input device: unknown")

            try:
                with sr.Microphone(device_index=device_index) as source:
                    if getattr(source, "stream", None) is None:
                        raise RuntimeError("Microphone stream is not available.")

                    recognizer.adjust_for_ambient_noise(source, duration=0.6)

                    if not INTRODUCED:
                        speak("Hello, my name is Sentinel. What is your name?")
                        INTRODUCED = True

                    while True:
                        try:
                            # Prevent the recognizer from transcribing Sentinel's own voice.
                            if _currently_speaking or not speech_queue.empty():
                                time.sleep(0.2)
                                continue

                            audio = recognizer.listen(source, timeout=4, phrase_time_limit=12)
                            text = _recognize_audio(audio)
                            if text is None:
                                continue
                            if len(text) < 2:
                                continue

                            memory.log_event(f"Heard: {text}")
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
            except Exception as exc:
                memory.log_event(f"Mic init error: {exc}")
                continue

        time.sleep(1.0)
