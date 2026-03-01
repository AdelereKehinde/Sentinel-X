import sys
import cv2
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QStackedWidget, QCheckBox, QLineEdit, QListWidget
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer, Qt
from threading import Thread

from ai_modules.vision_engine import cap, detect_objects, recognize_faces
from ai_modules.voice_engine import listen_loop
from ai_modules.memory_engine import memory
from backend.database import get_db

db = next(get_db())

class SentinelUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sentinel Prime")
        self.setGeometry(100, 100, 1280, 720)
        self.setStyleSheet("background-color: #020617; color: #22D3EE;")

        self.stack = QStackedWidget()
        self.main_screen = self.build_main_screen()
        self.settings_screen = self.build_settings_screen()

        self.stack.addWidget(self.main_screen)
        self.stack.addWidget(self.settings_screen)

        layout = QVBoxLayout()
        layout.addWidget(self.stack)
        self.setLayout(layout)

        # Camera Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_camera)
        self.timer.start(30)

    # ================= MAIN SCREEN =================
    def build_main_screen(self):
        screen = QWidget()
        layout = QHBoxLayout()

        # LEFT — AI CORE
        left_layout = QVBoxLayout()

        self.core_label = QLabel("●")
        self.core_label.setAlignment(Qt.AlignCenter)
        self.core_label.setStyleSheet("font-size: 120px; color: #22D3EE;")
        left_layout.addWidget(self.core_label)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.status_label)

        self.wave_label = QLabel("▁▂▃▄▅▆▇")
        self.wave_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.wave_label)

        # BUTTONS
        self.start_voice_btn = QPushButton("Start Voice")
        self.start_voice_btn.clicked.connect(self.start_voice)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))

        left_layout.addWidget(self.start_voice_btn)
        left_layout.addWidget(self.settings_btn)

        layout.addLayout(left_layout)

        # RIGHT — CAMERA + OBJECTS
        right_layout = QVBoxLayout()

        self.camera_label = QLabel()
        self.camera_label.setFixedSize(640, 480)
        right_layout.addWidget(self.camera_label)

        self.objects_list = QListWidget()
        right_layout.addWidget(self.objects_list)

        layout.addLayout(right_layout)
        screen.setLayout(layout)
        return screen

    # ================= SETTINGS SCREEN =================
    def build_settings_screen(self):
        screen = QWidget()
        layout = QVBoxLayout()

        self.mic_toggle = QCheckBox("Enable Microphone")
        self.mic_toggle.setChecked(True)

        self.cam_toggle = QCheckBox("Enable Camera")
        self.cam_toggle.setChecked(True)

        self.system_toggle = QCheckBox("Enable System Control")
        self.system_toggle.setChecked(False)

        self.file_toggle = QCheckBox("Enable File Access")
        self.file_toggle.setChecked(False)

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Allowed Folder Path")

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        layout.addWidget(self.mic_toggle)
        layout.addWidget(self.cam_toggle)
        layout.addWidget(self.system_toggle)
        layout.addWidget(self.file_toggle)
        layout.addWidget(self.folder_input)
        layout.addWidget(back_btn)
        screen.setLayout(layout)
        return screen

    # ================= CAMERA UPDATE =================
    def update_camera(self):
        if not self.cam_toggle.isChecked():
            return

        ret, frame = cap.read()
        if not ret:
            return

        # Face recognition
        face_locations, names = recognize_faces(frame)
        for (top, right, bottom, left), name in zip(face_locations, names):
            cv2.rectangle(frame, (left, top), (right, bottom), (255, 0, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        # Object detection
        frame, objects = detect_objects(frame)
        self.objects_list.clear()
        for obj in set(objects):
            self.objects_list.addItem(obj)

        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.camera_label.setPixmap(QPixmap.fromImage(qt_image))

    # ================= VOICE =================
    def start_voice(self):
        self.status_label.setText("Status: Listening")
        self.core_label.setStyleSheet("font-size: 120px; color: #FACC15;")
        voice_thread = Thread(target=listen_loop, daemon=True)
        voice_thread.start()


# ================= RUN APP =================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SentinelUI()
    window.show()
    sys.exit(app.exec_())