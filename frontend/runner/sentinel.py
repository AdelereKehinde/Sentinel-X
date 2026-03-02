import sys
import os
import time
from PyQt5.QtWidgets import QApplication
from threading import Thread

# ======================
# PATH SETUP
# ======================
RUNNER_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_ROOT = os.path.dirname(RUNNER_DIR)
PROJECT_ROOT = os.path.dirname(FRONTEND_ROOT)
sys.path.insert(0, FRONTEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

# ======================
# IMPORT UI & MODULES
# ======================
from ui.sentinel_ui import SentinelUI
from ai_modules.idle_thoughts import idle_engine
from ai_modules.voice_engine import speak, listen_loop

# ======================
# IDLE THOUGHT LOOP
# ======================
def run_idle_loop():
    """Continuously checks idle thoughts and speaks them immediately."""
    while True:
        idle_text = idle_engine.check_idle()  # returns string or None
        if idle_text:
            speak(idle_text)  # now sends to UI & speaks
        time.sleep(5)

# ======================
# MAIN UI
# ======================
def run_ui():
    app = QApplication(sys.argv)
    window = SentinelUI()
    window.show()
    sys.exit(app.exec_())

# ======================
# MAIN ENTRY
# ======================
if __name__ == "__main__":
    # Idle thoughts run in background
    idle_thread = Thread(target=run_idle_loop, daemon=True)
    idle_thread.start()

    # GUI must run in main thread
    run_ui()