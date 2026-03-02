import sys
import threading
from threading import Thread
from queue import Queue
from datetime import datetime
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QFrame, QLabel, QLineEdit, QTextEdit, QListWidget, QPushButton
)
import cv2

from ai_modules.memory_engine import memory
from ai_modules.vision_engine import camera, detect_faces, detect_objects, get_vision_status
from ai_modules.voice_engine import listen_loop, process_command, set_speaking_callback, set_ui_reply_callback
from ai_modules.idle_thoughts import idle_engine
from ai_modules.voice_engine import speak

# ==============================
# Sentinel Prime UI
# ==============================
class SentinelUI(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_queue = Queue()
        self.voice_started = False
        self.is_speaking = False
        self.mouth_toggle = False

        self.setWindowTitle("Sentinel Prime")
        self.setGeometry(140, 80, 1200, 780)
        self.setStyleSheet(self._theme())

        self._build_ui()
        self._setup_timers()
        self._setup_callbacks()
        self._initialize_camera()

        # auto-start voice recognition after UI fully loads
        QTimer.singleShot(2500, self.start_voice)

    # ------------------------------
    # UI Layout
    # ------------------------------
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(10)

        # Left panel
        left = QFrame()
        left.setObjectName("panel")
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(8)

        self.header_label = QLabel("SENTINEL PRIME")
        self.header_label.setObjectName("title")
        self.header_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.header_label)

        self.status_label = QLabel("Mode: Booting")
        self.status_label.setObjectName("muted")
        self.status_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.status_label)

        self.clock_label = QLabel("")
        self.clock_label.setObjectName("muted")
        self.clock_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.clock_label)

        self.robot_face = QLabel("◉   ◉")
        self.robot_face.setAlignment(Qt.AlignCenter)
        self.robot_face.setStyleSheet("font-size: 48px; color: #f8c784;")
        left_layout.addWidget(self.robot_face)

        self.robot_mouth = QLabel("━━━━━━")
        self.robot_mouth.setAlignment(Qt.AlignCenter)
        self.robot_mouth.setStyleSheet("font-size: 30px; color: #f59e0b;")
        left_layout.addWidget(self.robot_mouth)

        self.vision_status_label = QLabel(f"Vision: {get_vision_status()}")
        self.vision_status_label.setObjectName("muted")
        self.vision_status_label.setWordWrap(True)
        left_layout.addWidget(self.vision_status_label)

        self.face_count_label = QLabel("Faces: 0")
        self.face_count_label.setObjectName("muted")
        left_layout.addWidget(self.face_count_label)

        self.object_count_label = QLabel("Objects: 0")
        self.object_count_label.setObjectName("muted")
        left_layout.addWidget(self.object_count_label)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Sentinel conversation feed")
        left_layout.addWidget(self.chat_history)

        # Command input row
        cmd_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Type command...")
        self.command_input.returnPressed.connect(self.on_send_clicked)
        cmd_row.addWidget(self.command_input)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.on_send_clicked)
        cmd_row.addWidget(send_btn)
        left_layout.addLayout(cmd_row)

        # Right panel
        right = QFrame()
        right.setObjectName("panel")
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(8)

        self.camera_label = QLabel("Camera loading...")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(680, 480)
        self.camera_label.setStyleSheet("border: 1px solid #574136; border-radius: 8px;")
        right_layout.addWidget(self.camera_label)

        # Quick command buttons
        quick_row = QHBoxLayout()
        for label, cmd in [("Open Notepad", "open app notepad"),
                           ("Open Downloads", "open downloads"),
                           ("What time", "what time is it")]:
            btn = QPushButton(label)
            btn.setObjectName("secondary")
            btn.clicked.connect(lambda _, text=cmd: self.send_command(text))
            quick_row.addWidget(btn)
        right_layout.addLayout(quick_row)

        # Detected objects list
        right_layout.addWidget(QLabel("Detected Objects"))
        self.objects_list = QListWidget()
        self.objects_list.setMaximumHeight(160)
        right_layout.addWidget(self.objects_list)

        # Logs list
        right_layout.addWidget(QLabel("Recent Logs"))
        self.logs_list = QListWidget()
        right_layout.addWidget(self.logs_list)

        # Add panels to root layout
        root.addWidget(left, 2)
        root.addWidget(right, 3)

    # ------------------------------
    # Timers
    # ------------------------------
    def _setup_timers(self):
        self.camera_timer = QTimer()
        self.camera_timer.timeout.connect(self.update_camera)
        self.camera_timer.start(33)

        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.refresh_logs)
        self.log_timer.start(2000)

        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_ui_queue)
        self.queue_timer.start(100)

        self.mouth_timer = QTimer()
        self.mouth_timer.timeout.connect(self.animate_mouth)
        self.mouth_timer.start(180)

    # ------------------------------
    # Callbacks
    # ------------------------------
    def _setup_callbacks(self):
        set_speaking_callback(lambda speaking: self.ui_queue.put(("speaking", speaking)))
        set_ui_reply_callback(lambda text: self.ui_queue.put(("reply", text)))
        self.update_clock()
        self.refresh_logs()

    # ------------------------------
    # Camera
    # ------------------------------
    def _initialize_camera(self):
        if not getattr(camera, "running", False):
            camera.start()

    def update_camera(self):
        self.vision_status_label.setText(f"Vision: {get_vision_status()}")
        frame = camera.read()
        if frame is None:
            return

        frame, names = detect_faces(frame)
        self.face_count_label.setText(f"Faces: {len(names)}")

        frame, objects = detect_objects(frame)
        unique_objects = sorted(set(objects))
        self.object_count_label.setText(f"Objects: {len(unique_objects)}")
        self.objects_list.clear()
        for obj in unique_objects:
            self.objects_list.addItem(obj)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_image = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self.camera_label.setPixmap(QPixmap.fromImage(qt_image))

    # ------------------------------
    # Chat & commands
    # ------------------------------
    def append_chat(self, speaker, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_history.append(f"[{timestamp}] {speaker}: {message}")

    def send_command(self, text):
        command = text.strip()
        if not command:
            return
        self.append_chat("User", command)
        self.status_label.setText("Mode: Processing")
        threading.Thread(target=self._run_command, args=(command,), daemon=True).start()

    def _run_command(self, command):
        reply = process_command(command)  # backend reply
        if reply:
            # Update chat UI immediately
            self.ui_queue.put(("reply", reply))
            # Speak immediately
            speak(reply)
        self.ui_queue.put(("status", "Mode: Listening"))
    def process_ui_queue(self):
        while not self.ui_queue.empty():
            event, value = self.ui_queue.get()
            if event == "reply":
                self.append_chat("Sentinel", value)
                self.refresh_logs()
            elif event == "status":
                self.status_label.setText(value)
            elif event == "speaking":
                self.is_speaking = bool(value)

    def on_send_clicked(self):
        text = self.command_input.text()
        self.command_input.clear()
        self.send_command(text)

    
    def start_voice(self):
        if self.voice_started:
            return
        self.status_label.setText("Mode: Listening")
        # voice thread will pass results to send_command
        Thread(target=listen_loop, args=(self.send_command,), daemon=True).start()
        self.voice_started = True

    # ------------------------------
    # Mouth animation & clock
    # ------------------------------
    def animate_mouth(self):
        if not self.is_speaking:
            self.robot_mouth.setText("━━━━━━")
            return
        self.mouth_toggle = not self.mouth_toggle
        self.robot_mouth.setText("▁▂▃▂▁" if self.mouth_toggle else "▃▄▅▄▃")

    def update_clock(self):
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S  %d %b %Y"))

    def refresh_logs(self):
        logs = memory.get_logs()[-10:]
        self.logs_list.clear()
        for item in reversed(logs):
            self.logs_list.addItem(f"{item['time']} | {item['event']}")

    def closeEvent(self, event):
        camera.stop()
        event.accept()

    # ------------------------------
    # UI Theme
    # ------------------------------
    def _theme(self):
        return """
        QWidget {
            background: #121112;
            color: #f6efe8;
            font-family: Segoe UI, Arial;
            font-size: 13px;
        }
        QFrame#panel {
            background: #1e1a1a;
            border: 1px solid #4f3d31;
            border-radius: 12px;
        }
        QLabel#title {
            font-size: 28px;
            font-weight: 700;
            color: #f7a95b;
        }
        QLabel#muted {
            color: #d9c7b5;
        }
        QTextEdit, QListWidget, QLineEdit {
            background: #151213;
            border: 1px solid #544134;
            border-radius: 8px;
            padding: 7px;
            color: #f5e9dd;
        }
        QPushButton {
            background: #f59e0b;
            color: #25180f;
            border: 0;
            border-radius: 8px;
            padding: 8px 11px;
            font-weight: 700;
        }
        QPushButton:hover {
            background: #fbbf24;
        }
        QPushButton#secondary {
            background: #332721;
            color: #f3e6da;
            border: 1px solid #5f4a3b;
        }
        """


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SentinelUI()
    window.show()

    # Idle thoughts in background
    def idle_loop():
        while True:
            if not window.is_speaking:
                text = idle_engine.check_idle()
                if text:
                    speak(text)
            threading.Event().wait(5)

    threading.Thread(target=idle_loop, daemon=True).start()
    sys.exit(app.exec_())