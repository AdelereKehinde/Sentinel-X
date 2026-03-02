import sys
import os
from PyQt5.QtWidgets import QApplication
from threading import Thread
import time

RUNNER_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_ROOT = os.path.dirname(RUNNER_DIR)
PROJECT_ROOT = os.path.dirname(FRONTEND_ROOT)
sys.path.insert(0, FRONTEND_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from ui.sentinel_ui import SentinelUI

from ai_modules.idle_thoughts import idle_engine


def run_idle_loop():
    while True:
        idle_engine.check_idle()
        time.sleep(5)


def run_ui():
    app = QApplication(sys.argv)
    window = SentinelUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    idle_thread = Thread(target=run_idle_loop)
    idle_thread.daemon = True
    idle_thread.start()

    # Qt UI must run in the main thread.
    run_ui()
