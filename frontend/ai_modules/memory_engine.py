import json
import os
from datetime import datetime

MEMORY_FILE = "models/memory.json"


class MemoryEngine:
    def __init__(self):
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump({"users": [], "logs": [], "conversations": {}}, f)

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            self.memory = json.load(f)

        self.memory.setdefault("users", [])
        self.memory.setdefault("logs", [])
        self.memory.setdefault("conversations", {})

    def remember_user(self, name):
        if name.lower() not in [u.lower() for u in self.memory["users"]]:
            self.memory["users"].append(name)
            self._save()
            return f"New user detected: {name}"
        return f"I know you, {name}"

    def greet_user(self, name):
        if name.lower() in [u.lower() for u in self.memory["users"]]:
            return f"Welcome back, {name}"
        self.memory["users"].append(name)
        self._save()
        return f"Hello {name}, I am Sentinel. I will remember you."

    def get_users(self):
        return self.memory["users"]

    def log_event(self, event):
        self.memory["logs"].append(
            {
                "event": event,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self._save()

    def remember_conversation(self, user, message, reply):
        if user not in self.memory["conversations"]:
            self.memory["conversations"][user] = []

        self.memory["conversations"][user].append(
            {
                "user": message,
                "sentinel": reply,
            }
        )
        self._save()

    def get_last_conversation(self, user):
        try:
            return self.memory["conversations"][user][-1]
        except Exception:
            return None

    def get_logs(self):
        return self.memory["logs"]

    def _save(self):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=4)


memory = MemoryEngine()
