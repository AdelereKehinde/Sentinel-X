import time
from ai_modules.voice_engine import speak
from ai_modules.memory_engine import memory

class AutonomousController:
    def __init__(self):
        self.last_objects = []
        self.last_scan_time = 0
        self.scan_interval = 8  # seconds
        self.enabled = True

    def process_environment(self, objects, faces):
        """
        Called from vision engine every frame
        """
        if not self.enabled:
            return

        current_time = time.time()

        # Limit how often robot speaks
        if current_time - self.last_scan_time < self.scan_interval:
            return

        self.last_scan_time = current_time

        # ===== FACE REACTION =====
        for name in faces:
            if name != "Unknown":
                speak(f"I can see you, {name}")
                memory.log_event(f"Autonomous: saw {name}")
                return

        # ===== OBJECT REACTION =====
        unique_objects = list(set(objects))

        if "person" in unique_objects:
            speak("I detect a person nearby.")

        elif "laptop" in unique_objects:
            speak("You are working on your laptop.")

        elif "phone" in unique_objects:
            speak("I see a phone.")

        elif "book" in unique_objects:
            speak("You are reading.")

        elif unique_objects:
            speak(f"I can see {unique_objects[0]}")

controller = AutonomousController()