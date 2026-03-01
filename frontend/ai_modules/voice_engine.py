from multiprocessing import context
import speech_recognition as sr
import pyttsx3
import requests
from ai_modules.memory_engine import memory
from ai_modules.system_control import execute_command
from ai_modules.idle_thoughts import idle_engine
idle_engine.update_activity()

WAKE_WORD = "sentinel"
BACKEND_URL = "http://127.0.0.1:8000/brain"
AUTONOMOUS_HEARING = True

recognizer = sr.Recognizer()
engine = pyttsx3.init()
engine.setProperty("rate", 170)

def speak(text):
    engine.say(text)
    engine.runAndWait()
    memory.log_event(f"Sentinel said: {text}")

def process_command(command):
    command = command.lower()

    memory.log_event(f"User said: {command}")

    # SYSTEM FIRST (local robot actions)
    system_response = execute_command(command)
    if system_response:
        speak(system_response)
        return

# AI BRAIN (OpenRouter via backend)
reply = "I am thinking."
try:
    response = requests.post(
        BACKEND_URL,
        json={
            "message": command,
            "context": context
        }
    )
    reply = response.json().get("response", "I am thinking.")
except:
    reply = "My brain server is not reachable."

memory.remember_conversation(user_name, command, reply)
speak(reply)

def listen_loop():
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)

        while True:
            try:
                audio = recognizer.listen(source, timeout=5)
                text = recognizer.recognize_google(audio).lower()

                if WAKE_WORD in text or AUTONOMOUS_HEARING:
                    speak("Listening.")
                    memory.log_event("Wake word detected")

                    audio = recognizer.listen(source)
                    command = recognizer.recognize_google(audio)
                    memory.log_event(f"User said: {command}")

                    process_command(command)

            except sr.WaitTimeoutError:
                continue
            except:
                continue