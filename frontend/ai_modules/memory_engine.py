from datetime import datetime

class MemoryEngine:
    def __init__(self):
        # Runtime-only memory. This intentionally avoids saving to disk.
        self.memory = {
            "users": [],
            "logs": [],
            "conversations": {},
        }

    def remember_user(self, name):
        clean_name = (name or "").strip()
        if not clean_name:
            return "Tell me your name clearly."

        known = [u.lower() for u in self.memory["users"]]
        if clean_name.lower() not in known:
            self.memory["users"].append(clean_name)
            return f"Welcome, {clean_name}."
        return f"Welcome back, {clean_name}."

    def greet_user(self, name):
        clean_name = (name or "").strip()
        if not clean_name:
            return "Hello, I am Sentinel. What is your name?"

        if clean_name.lower() in [u.lower() for u in self.memory["users"]]:
            return f"Welcome back, {clean_name}."
        self.memory["users"].append(clean_name)
        return f"Welcome, {clean_name}."

    def get_users(self):
        return list(self.memory["users"])

    def log_event(self, event):
        self.memory["logs"].append(
            {
                "event": str(event),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    def remember_conversation(self, user, message, reply):
        if user not in self.memory["conversations"]:
            self.memory["conversations"][user] = []

        self.memory["conversations"][user].append(
            {
                "user": str(message),
                "sentinel": str(reply),
            }
        )

    def get_last_conversation(self, user):
        try:
            return self.memory["conversations"][user][-1]
        except Exception:
            return None

    def get_logs(self):
        return list(self.memory["logs"])

    def get_recent_conversations(self, user="user", limit=6):
        rows = self.memory["conversations"].get(user, [])
        return rows[-limit:]

    def get_recent_logs(self, limit=10):
        return self.memory["logs"][-limit:]

    def get_current_user(self):
        return self.memory["users"][-1] if self.memory["users"] else None

    # Compatibility no-op: code may still call _save().
    def _save(self):
        return None

memory = MemoryEngine()
