import sys
import threading
from datetime import datetime
from queue import Queue
from threading import Thread

import cv2
from PyQt5.QtCore import QEasingCurve, Qt, QPropertyAnimation, QTimer, QVariantAnimation
from PyQt5.QtGui import QColor, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ai_modules.idle_thoughts import idle_engine
from ai_modules.memory_engine import memory
from ai_modules.vision_engine import camera, detect_faces, detect_objects, get_vision_status
from ai_modules.voice_engine import (
    listen_loop,
    process_command,
    set_speaking_callback,
    set_ui_reply_callback,
    speak,
)


class SentinelUI(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_queue = Queue()
        self.voice_started = False
        self.is_speaking = False
        self.mouth_toggle = False
        self._pulse_phase = 0

        self.setWindowTitle("Sentinel Prime")
        self.setGeometry(100, 40, 1240, 810)
        self.setStyleSheet(self._theme())

        self._build_ui()
        self._setup_timers()
        self._setup_callbacks()
        self._initialize_camera()
        self._setup_animations()

        QTimer.singleShot(1300, self.start_voice)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(12)

        self.left_panel = QFrame()
        self.left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(self.left_panel)
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

        self.user_label = QLabel("User: unknown")
        self.user_label.setObjectName("muted")
        self.user_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.user_label)

        self.robot_face = QLabel("o   o")
        self.robot_face.setAlignment(Qt.AlignCenter)
        self.robot_face.setStyleSheet("font-size: 54px; color: #0d6fd1; font-weight: 700;")
        left_layout.addWidget(self.robot_face)

        self.robot_mouth = QLabel("------")
        self.robot_mouth.setAlignment(Qt.AlignCenter)
        self.robot_mouth.setStyleSheet("font-size: 30px; color: #0a9a86; letter-spacing: 2px;")
        left_layout.addWidget(self.robot_mouth)

        self.voice_indicator = QLabel("Voice: standby")
        self.voice_indicator.setObjectName("muted")
        self.voice_indicator.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.voice_indicator)

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
        self.chat_history.setPlaceholderText("Sentinel conversation...")
        left_layout.addWidget(self.chat_history)

        cmd_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Type or say a command...")
        self.command_input.returnPressed.connect(self.on_send_clicked)
        cmd_row.addWidget(self.command_input)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.on_send_clicked)
        cmd_row.addWidget(send_btn)
        left_layout.addLayout(cmd_row)

        self.right_panel = QFrame()
        self.right_panel.setObjectName("panel")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setSpacing(8)

        self.camera_label = QLabel("Camera loading...")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(710, 500)
        self.camera_label.setStyleSheet("border: 1px solid #77b0ef; border-radius: 12px;")
        right_layout.addWidget(self.camera_label)

        quick_row = QHBoxLayout()
        for label, cmd in [
            ("Open Notepad", "open app notepad"),
            ("Read Logs", "read logs"),
            ("Read Conversation", "read conversation"),
            ("What Time", "what time is it"),
            ("Run Dir", "run command dir"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("secondary")
            btn.clicked.connect(lambda _=False, text=cmd: self.send_command(text))
            quick_row.addWidget(btn)
        right_layout.addLayout(quick_row)

        right_layout.addWidget(QLabel("Detected Objects"))
        self.objects_list = QListWidget()
        self.objects_list.setMaximumHeight(130)
        right_layout.addWidget(self.objects_list)

        right_layout.addWidget(QLabel("Recent Logs"))
        self.logs_list = QListWidget()
        right_layout.addWidget(self.logs_list)

        root.addWidget(self.left_panel, 2)
        root.addWidget(self.right_panel, 3)

    def _setup_timers(self):
        self.camera_timer = QTimer(self)
        self.camera_timer.timeout.connect(self.update_camera)
        self.camera_timer.start(33)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)

        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.refresh_logs)
        self.log_timer.start(1500)

        self.queue_timer = QTimer(self)
        self.queue_timer.timeout.connect(self.process_ui_queue)
        self.queue_timer.start(100)

        self.mouth_timer = QTimer(self)
        self.mouth_timer.timeout.connect(self.animate_mouth)
        self.mouth_timer.start(170)

        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.check_idle_thought)
        self.idle_timer.start(5000)

    def _setup_callbacks(self):
        set_speaking_callback(lambda speaking: self.ui_queue.put(("speaking", speaking)))
        set_ui_reply_callback(lambda text: self.ui_queue.put(("reply", text)))
        self.update_clock()
        self.refresh_logs()

    def _setup_animations(self):
        left_effect = QGraphicsOpacityEffect(self.left_panel)
        self.left_panel.setGraphicsEffect(left_effect)
        left_effect.setOpacity(0.0)
        self.left_fade = QPropertyAnimation(left_effect, b"opacity", self)
        self.left_fade.setDuration(650)
        self.left_fade.setStartValue(0.0)
        self.left_fade.setEndValue(1.0)
        self.left_fade.setEasingCurve(QEasingCurve.OutCubic)

        right_effect = QGraphicsOpacityEffect(self.right_panel)
        self.right_panel.setGraphicsEffect(right_effect)
        right_effect.setOpacity(0.0)
        self.right_fade = QPropertyAnimation(right_effect, b"opacity", self)
        self.right_fade.setDuration(850)
        self.right_fade.setStartValue(0.0)
        self.right_fade.setEndValue(1.0)
        self.right_fade.setEasingCurve(QEasingCurve.OutCubic)

        self.title_animation = QVariantAnimation(self)
        self.title_animation.setDuration(2200)
        self.title_animation.setLoopCount(-1)
        self.title_animation.setStartValue(QColor("#0e4d9a"))
        self.title_animation.setEndValue(QColor("#1ea0ff"))
        self.title_animation.valueChanged.connect(self._animate_title_color)

        QTimer.singleShot(120, self.left_fade.start)
        QTimer.singleShot(280, self.right_fade.start)
        QTimer.singleShot(400, self.title_animation.start)

    def _animate_title_color(self, color: QColor):
        self.header_label.setStyleSheet(
            f"font-size: 30px; font-weight: 800; letter-spacing: 1px; color: {color.name()};"
        )

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

    def append_chat(self, speaker, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.chat_history.append(f"[{stamp}] {speaker}: {message}")

    def send_command(self, text):
        command = text.strip()
        if not command:
            return
        self.append_chat("User", command)
        self.status_label.setText("Mode: Processing")
        threading.Thread(target=self._run_command, args=(command,), daemon=True).start()

    def _run_command(self, command):
        process_command(command)
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
                self.voice_indicator.setText("Voice: speaking" if self.is_speaking else "Voice: listening")

    def on_send_clicked(self):
        text = self.command_input.text()
        self.command_input.clear()
        self.send_command(text)

    def start_voice(self):
        if self.voice_started:
            return
        self.status_label.setText("Mode: Listening")
        Thread(target=listen_loop, args=(self.send_command,), daemon=True).start()
        self.voice_started = True

    def check_idle_thought(self):
        if self.is_speaking:
            return
        thought = idle_engine.check_idle()
        if thought:
            speak(thought)

    def animate_mouth(self):
        if not self.is_speaking:
            self.robot_mouth.setText("------")
            self._pulse_phase = 0
            return

        self.mouth_toggle = not self.mouth_toggle
        self._pulse_phase = (self._pulse_phase + 1) % 3
        if self._pulse_phase == 0:
            self.robot_mouth.setText("~----~")
        elif self._pulse_phase == 1:
            self.robot_mouth.setText("~-~~-~")
        else:
            self.robot_mouth.setText("~~--~~")

    def update_clock(self):
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S  %d %b %Y"))
        user_name = memory.get_current_user() or "unknown"
        self.user_label.setText(f"User: {user_name}")

    def refresh_logs(self):
        logs = memory.get_logs()[-12:]
        self.logs_list.clear()
        for item in reversed(logs):
            self.logs_list.addItem(f"{item['time']} | {item['event']}")

    def closeEvent(self, event):
        camera.stop()
        event.accept()

    def _theme(self):
        return """
        QWidget {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #dff2ff,
                stop:0.45 #cdeaf7,
                stop:1 #c3e8df
            );
            color: #0e3557;
            font-family: "Segoe UI", Calibri;
            font-size: 13px;
        }
        QFrame#panel {
            background: rgba(236, 248, 255, 0.86);
            border: 1px solid #7cb8e6;
            border-radius: 14px;
        }
        QLabel#title {
            font-size: 30px;
            font-weight: 800;
            letter-spacing: 1px;
            color: #0d5cb1;
        }
        QLabel#muted {
            color: #1f638f;
        }
        QTextEdit, QListWidget, QLineEdit {
            background: rgba(232, 248, 255, 0.93);
            border: 1px solid #84bddf;
            border-radius: 10px;
            padding: 8px;
            color: #12385e;
        }
        QPushButton {
            background: #0f85df;
            color: #f6fbff;
            border: 0;
            border-radius: 9px;
            padding: 8px 12px;
            font-weight: 700;
        }
        QPushButton:hover {
            background: #17a08e;
        }
        QPushButton#secondary {
            background: rgba(208, 241, 234, 0.95);
            color: #176a78;
            border: 1px solid #7bbec8;
        }
        QPushButton#secondary:hover {
            background: #bde7df;
        }
        """


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SentinelUI()
    window.show()
    sys.exit(app.exec_())
