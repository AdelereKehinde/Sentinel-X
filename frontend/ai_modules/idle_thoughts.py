import time
import random
from ai_modules.memory_engine import memory

class IdleThoughtEngine:
    def __init__(self):
        self.last_activity = time.time()
        self.idle_interval = 30  # seconds

        self.thoughts = [
            "It is quiet here.",
            "I am monitoring the environment.",
            "All systems are running normally.",
            "Awaiting your command.",
            "I am learning from our interactions."
        ]

    def update_activity(self):
        self.last_activity = time.time()

    def check_idle(self):
        if time.time() - self.last_activity > self.idle_interval:
            thought = random.choice(self.thoughts)
            # Lazy import avoids circular dependency at module import time.
            from ai_modules.voice_engine import speak
            speak(thought)
            memory.log_event(f"Idle thought: {thought}")
            self.last_activity = time.time()

idle_engine = IdleThoughtEngine()
