import os
from typing import Callable, Optional

import pyttsx3
import requests
import speech_recognition as sr

from ai_modules.memory_engine import memory
from ai_modules.system_control import execute_command

BACKEND_URL = "http://127.0.0.1:8000/brain"
AUTONOMOUS_HEARING = True
INTRODUCED = False
_speaking_callback: Optional[Callable[[bool], None]] = None

recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 300
recognizer.pause_threshold = 0.7
recognizer.non_speaking_duration = 0.4

engine = pyttsx3.init()
engine.setProperty("rate", 170)


def set_speaking_callback(callback: Callable[[bool], None]):
    global _speaking_callback
    _speaking_callback = callback


def _notify_speaking(is_speaking: bool):
    if _speaking_callback is not None:
        try:
            _speaking_callback(is_speaking)
        except Exception:
            pass


def speak(text):
    _notify_speaking(True)
    try:
        engine.say(text)
        engine.runAndWait()
    finally:
        _notify_speaking(False)
    memory.log_event(f"Sentinel said: {text}")


def process_command(command):
    command = command.lower().strip()
    if not command:
        return None

    memory.log_event(f"User said: {command}")

    # Lazy import breaks the idle_thoughts <-> voice_engine cycle.
    from ai_modules.idle_thoughts import idle_engine

    idle_engine.update_activity()

    system_response = execute_command(command)
    if system_response:
        speak(system_response)
        return system_response

    reply = "I am thinking."
    try:
        response = requests.post(
            BACKEND_URL,
            json={"input_text": command},
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        reply = payload.get("response", "I am thinking.")
    except requests.RequestException as exc:
        reply = f"My brain server is not reachable. {exc}"

    memory.remember_conversation("user", command, reply)
    speak(reply)
    return reply


def listen_loop():
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
                audio = recognizer.listen(source, timeout=3, phrase_time_limit=8)
                text = recognizer.recognize_google(audio).lower().strip()
                if len(text) < 2:
                    continue

                if AUTONOMOUS_HEARING:
                    process_command(text)

            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except Exception as exc:
                memory.log_event(f"Voice loop error: {exc}")
                continue
