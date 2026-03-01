import os
import json
from datetime import datetime

MEMORY_FILE = "models/memory.json"

class MemoryEngine:
    def __init__(self):
        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "w") as f:
                json.dump({"users": [], "logs": []}, f)

        with open(MEMORY_FILE, "r") as f:
            self.memory = json.load(f)

    # ================= USERS =================
    def remember_user(self, name):
        if name.lower() not in [u.lower() for u in self.memory["users"]]:
            self.memory["users"].append(name)
            self._save()
            return f"New user detected: {name}"
        else:
            return f"I know you, {name}"

    def greet_user(self, name):
        if name.lower() in [u.lower() for u in self.memory["users"]]:
            return f"Welcome back, {name}"
        else:
            self.memory["users"].append(name)
            self._save()
            return f"Hello {name}, I am Sentinel. I will remember you."
        
    def get_users(self):
        return self.memory["users"]

    # ================= LOGS =================
    def log_event(self, event):
        self.memory["logs"].append({
            "event": event,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self._save()

    # ================= CONVERSATION MEMORY =================
def remember_conversation(self, user, message, reply):
    if "conversations" not in self.memory:
        self.memory["conversations"] = {}

    if user not in self.memory["conversations"]:
        self.memory["conversations"][user] = []

    self.memory["conversations"][user].append({
        "user": message,
        "sentinel": reply
    })

    self._save()

def get_last_conversation(self, user):
    try:
        return self.memory["conversations"][user][-1]
    except:
        return None

    def get_logs(self):
        return self.memory["logs"]

    # ================= SAVE =================
    def _save(self):
        with open(MEMORY_FILE, "w") as f:
            json.dump(self.memory, f, indent=4)

memory = MemoryEngine()