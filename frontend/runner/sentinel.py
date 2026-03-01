import sys
from PyQt5.QtWidgets import QApplication
from threading import Thread

from ui.sentinel_ui import SentinelUI
from ai_modules.voice_engine import listen_loop
from ai_modules.vision_engine import start_vision
from ai_modules.idle_thoughts import idle_engine
import time

def run_idle_loop():
    while True:
        idle_engine.check_idle()
        time.sleep(5)

# ================= RUN UI =================
def run_ui():
    app = QApplication(sys.argv)
    window = SentinelUI()
    window.show()
    sys.exit(app.exec_())

# ================= RUN VOICE =================
def run_voice():
    listen_loop()

# ================= RUN VISION =================
def run_vision():
    start_vision()

# ================= MAIN =================
if __name__ == "__main__":
    # Threads for parallel execution
    ui_thread = Thread(target=run_ui)
    ui_thread.start()

    voice_thread = Thread(target=run_voice)
    voice_thread.daemon = True
    voice_thread.start()

    vision_thread = Thread(target=run_vision)
    vision_thread.daemon = True
    vision_thread.start()

    idle_thread = Thread(target=run_idle_loop)
    idle_thread.daemon = True
    idle_thread.start()