from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor
import random
import time

class EmotionEngine:
    """
    Controls Sentinel's AI core color and emotion state
    """
    def __init__(self, core_label, status_label):
        self.core_label = core_label
        self.status_label = status_label
        self.current_emotion = "neutral"
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_emotion)
        self.timer.start(1000)  # update every second

    def update_emotion(self):
        """
        Simple logic for AI core emotions:
        - Listening → yellow
        - Thinking → blue
        - Speaking → green
        - Neutral → cyan (idle)
        - Excited → magenta
        """
        if "Listening" in self.status_label.text():
            self.set_core_color("#FACC15")  # yellow
            self.current_emotion = "listening"
        elif "Processing" in self.status_label.text():
            self.set_core_color("#3B82F6")  # blue
            self.current_emotion = "thinking"
        elif "Speaking" in self.status_label.text():
            self.set_core_color("#10B981")  # green
            self.current_emotion = "speaking"
        else:
            # idle → neutral
            colors = ["#22D3EE", "#F472B6", "#EAB308"]
            self.set_core_color(random.choice(colors))
            self.current_emotion = "neutral"

    def set_core_color(self, hex_color):
        self.core_label.setStyleSheet(f"font-size: 120px; color: {hex_color};")