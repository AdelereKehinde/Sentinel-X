import os
import threading
from queue import Queue
from typing import Callable, Optional

import pyttsx3
import requests
import speech_recognition as sr

from ai_modules.memory_engine import memory
from ai_modules.system_control import execute_command

# ==============================
# CONFIG
# ==============================
BACKEND_URL = "http://127.0.0.1:8000/brain"
AUTONOMOUS_HEARING = True

# ==============================
# STATE
# ==============================
_speaking_callback: Optional[Callable[[bool], None]] = None
_ui_reply_callback: Optional[Callable[[str], None]] = None

speech_queue: Queue = Queue()

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 300
recognizer.pause_threshold = 0.7

engine = pyttsx3.init()
engine.setProperty("rate", 170)
engine.setProperty("volume", 1.0)

voices = engine.getProperty("voices")
engine.setProperty("voice", voices[0].id)  # change index if needed

INTRODUCED = False


# ==============================
# CALLBACKS
# ==============================
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


# ==============================
# SPEECH WORKER (NON-BLOCKING)
# ==============================
def _speech_worker():
    while True:
        text = speech_queue.get()
        if text is None:
            break

        _notify_speaking(True)

        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            memory.log_event(f"TTS error: {e}")
        finally:
            _notify_speaking(False)
            speech_queue.task_done()


threading.Thread(target=_speech_worker, daemon=True).start()


def speak(text: str):
    """Speak ANY text and log it."""
    if not text:
        return

    speech_queue.put(text)
    memory.log_event(f"{text}")

    # Also push to UI chat if available
    if _ui_reply_callback:
        _ui_reply_callback(text)


# ==============================
# MAIN COMMAND PROCESSOR
# ==============================
def process_command(command: str):
    command = command.lower().strip()
    if not command:
        return None

    memory.log_event(f"User said: {command}")

    # 1️⃣ SYSTEM COMMANDS FIRST
    system_response = execute_command(command)
    if system_response:
        memory.remember_conversation("user", command, system_response)
        speak(system_response)
        return system_response

    # 2️⃣ BACKEND AI BRAIN
    reply = "Processing your request."

    try:
        response = requests.post(
            BACKEND_URL,
            json={"input_text": command},
            timeout=30
        )
        response.raise_for_status()
        payload = response.json()
        reply = payload.get("response", "Sorry, I could not find anything.")
    except Exception as e:
        reply = f"Error fetching response: {e}"

    memory.remember_conversation("user", command, reply)
    speak(reply)
    return reply


def listen_loop(command_callback=None):
    """Continuously listen for voice commands."""
    global INTRODUCED

    mic_index = os.getenv("MIC_INDEX")
    device_index = int(mic_index) if mic_index and mic_index.isdigit() else None

    with sr.Microphone(device_index=device_index) as source:
        recognizer.adjust_for_ambient_noise(source, duration=1.2)

        if not INTRODUCED:
            speak("My name is Sentinel. I am online and listening.")
            INTRODUCED = True

        while True:
            try:
                audio = recognizer.listen(
                    source,
                    timeout=3,
                    phrase_time_limit=8
                )

                text = recognizer.recognize_google(audio).lower().strip()
                if len(text) < 2:
                    continue

                if AUTONOMOUS_HEARING and command_callback:
                    # send voice input to the UI command processor
                    command_callback(text)

            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except Exception as exc:
                memory.log_event(f"Voice loop error: {exc}")
                continue


def speak_log_watcher():
    """Speaks any new log entries automatically."""
    last_count = 0

    while True:
        logs = memory.get_logs()

        if len(logs) > last_count:
            new_logs = logs[last_count:]

            for item in new_logs:
                text = item.get("event", "")
                if text and not text.lower().startswith("user said"):
                    speak(text)

            last_count = len(logs)


# Start log watcher thread
threading.Thread(target=speak_log_watcher, daemon=True).start()