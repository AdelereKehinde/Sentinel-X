import sys
import os
from PyQt5.QtWidgets import QApplication

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
    # GUI must run in main thread.
    run_ui()
