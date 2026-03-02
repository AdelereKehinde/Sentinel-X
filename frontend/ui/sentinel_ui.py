import sys
from datetime import datetime
from queue import Queue
from threading import Thread

import cv2
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai_modules.memory_engine import memory
from ai_modules.vision_engine import cap, detect_objects, get_vision_status, recognize_faces
from ai_modules.voice_engine import listen_loop, process_command, set_speaking_callback


class SentinelUI(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_queue = Queue()
        self.voice_started = False
        self.is_speaking = False
        self.mouth_toggle = False

        self.setWindowTitle("Sentinel Prime")
        self.setGeometry(140, 80, 1080, 730)
        self.setStyleSheet(self._theme())

        root = QHBoxLayout(self)
        root.setSpacing(10)

        left = QFrame()
        left.setObjectName("panel")
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(8)

        header = QLabel("SENTINEL PRIME")
        header.setObjectName("title")
        header.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(header)

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
        self.robot_face.setStyleSheet("font-size: 46px; color: #f8c784;")
        left_layout.addWidget(self.robot_face)

        self.robot_mouth = QLabel("━━━━━━")
        self.robot_mouth.setAlignment(Qt.AlignCenter)
        self.robot_mouth.setStyleSheet("font-size: 28px; color: #f59e0b;")
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

        cmd_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Type command...")
        self.command_input.returnPressed.connect(self.on_send_clicked)
        cmd_row.addWidget(self.command_input)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.on_send_clicked)
        cmd_row.addWidget(send_btn)
        left_layout.addLayout(cmd_row)

        right = QFrame()
        right.setObjectName("panel")
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(8)

        self.camera_label = QLabel("Camera loading...")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(640, 430)
        self.camera_label.setStyleSheet("border: 1px solid #574136; border-radius: 8px;")
        right_layout.addWidget(self.camera_label)

        quick_row = QHBoxLayout()
        for label, cmd in [
            ("Open Notepad", "open app notepad"),
            ("Open Downloads", "open downloads"),
            ("What time", "what time is it"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("secondary")
            btn.clicked.connect(lambda _=False, text=cmd: self.send_command(text))
            quick_row.addWidget(btn)
        right_layout.addLayout(quick_row)

        right_layout.addWidget(QLabel("Detected Objects"))
        self.objects_list = QListWidget()
        self.objects_list.setMaximumHeight(140)
        right_layout.addWidget(self.objects_list)

        right_layout.addWidget(QLabel("Recent Logs"))
        self.logs_list = QListWidget()
        right_layout.addWidget(self.logs_list)

        root.addWidget(left, 2)
        root.addWidget(right, 3)

        self.camera_timer = QTimer()
        self.camera_timer.timeout.connect(self.update_camera)
        self.camera_timer.start(33)

        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.refresh_logs)
        self.log_timer.start(1800)

        self.queue_timer = QTimer()
        self.queue_timer.timeout.connect(self.process_ui_queue)
        self.queue_timer.start(100)

        self.mouth_timer = QTimer()
        self.mouth_timer.timeout.connect(self.animate_mouth)
        self.mouth_timer.start(180)

        set_speaking_callback(lambda speaking: self.ui_queue.put(("speaking", speaking)))
        self.update_clock()
        self.refresh_logs()

        # Auto-start listening with no button required.
        QTimer.singleShot(1200, self.start_voice)

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

    def update_clock(self):
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S  %d %b %Y"))

    def refresh_logs(self):
        logs = memory.get_logs()[-10:]
        self.logs_list.clear()
        for item in reversed(logs):
            self.logs_list.addItem(f"{item['time']} | {item['event']}")

    def animate_mouth(self):
        if not self.is_speaking:
            self.robot_mouth.setText("━━━━━━")
            return
        self.mouth_toggle = not self.mouth_toggle
        self.robot_mouth.setText("▁▂▃▂▁" if self.mouth_toggle else "▃▄▅▄▃")

    def update_camera(self):
        self.vision_status_label.setText(f"Vision: {get_vision_status()}")
        ret, frame = cap.read()
        if not ret:
            return

        face_locations, names = recognize_faces(frame)
        self.face_count_label.setText(f"Faces: {len(names)}")
        for (top, right, bottom, left), name in zip(face_locations, names):
            cv2.rectangle(frame, (left, top), (right, bottom), (255, 140, 80), 2)
            cv2.putText(
                frame,
                name,
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 140, 80),
                2,
            )

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

    def append_chat(self, speaker, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_history.append(f"[{timestamp}] {speaker}: {message}")

    def send_command(self, text):
        command = text.strip()
        if not command:
            return
        self.append_chat("User", command)
        self.status_label.setText("Mode: Processing")
        Thread(target=self._run_command, args=(command,), daemon=True).start()

    def _run_command(self, command):
        reply = process_command(command)
        if reply:
            self.ui_queue.put(("reply", reply))
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
        Thread(target=listen_loop, daemon=True).start()
        self.voice_started = True


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SentinelUI()
    window.show()
    sys.exit(app.exec_())
