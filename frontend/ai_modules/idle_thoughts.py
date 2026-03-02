import time
import random
from ai_modules.memory_engine import memory

class IdleThoughtEngine:
    def __init__(self):
        self.last_activity = time.time()
        self.idle_interval = 22  # seconds

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
            memory.log_event(f"Idle thought: {thought}")
            self.last_activity = time.time()
            return thought
        return None

idle_engine = IdleThoughtEngine()
