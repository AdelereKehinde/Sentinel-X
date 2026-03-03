import sys
import threading
import math
from datetime import datetime
from queue import Queue
from threading import Thread
import time

import cv2
from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QTimer, QVariantAnimation,
    QEasingCurve, QPoint, QRect, QParallelAnimationGroup,
    QSequentialAnimationGroup, QPauseAnimation, pyqtProperty
)
from PyQt5.QtGui import (
    QColor, QImage, QPixmap, QTextCursor, QFont, QPainter,
    QLinearGradient, QBrush, QPen, QRadialGradient, QPalette,
    QFontDatabase, QTransform, QCursor
)
from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QTextEdit, QVBoxLayout, QWidget,
    QGraphicsDropShadowEffect, QGraphicsBlurEffect, QGraphicsOpacityEffect
)

from ai_modules.idle_thoughts import idle_engine
from ai_modules.memory_engine import memory
from ai_modules.vision_engine import camera, detect_faces, detect_objects, get_vision_status
from ai_modules.voice_engine import (
    listen_loop, process_command, set_speaking_callback,
    set_ui_reply_callback, speak
)


class AnimatedRobotEye(QLabel):
    """Custom animated robot eye widget"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.pupil_offset = 0
        self.blink = 0
        self.glow_intensity = 0.5
        self.scan_line = 0
        self.setMinimumSize(60, 60)
        self.setMaximumSize(80, 80)
        
        # Animation timers
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.update_scan)
        self.scan_timer.start(50)
        
        self.glow_timer = QTimer(self)
        self.glow_timer.timeout.connect(self.update_glow)
        self.glow_timer.start(100)
        
    def update_scan(self):
        self.scan_line = (self.scan_line + 5) % 120
        self.update()
        
    def update_glow(self):
        self.glow_intensity = 0.5 + 0.3 * math.sin(time.time() * 3)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        center_x, center_y = w // 2, h // 2
        radius = min(w, h) // 2 - 5
        
        # Outer glow effect
        glow_gradient = QRadialGradient(center_x, center_y, radius + 10)
        glow_gradient.setColorAt(0, QColor(0, 200, 255, int(50 * self.glow_intensity)))
        glow_gradient.setColorAt(1, QColor(0, 100, 200, 0))
        painter.setBrush(QBrush(glow_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center_x - radius - 5, center_y - radius - 5, 
                           radius * 2 + 10, radius * 2 + 10)
        
        # Outer shell
        gradient = QRadialGradient(center_x - 3, center_y - 3, radius + 5)
        gradient.setColorAt(0, QColor(220, 240, 255))
        gradient.setColorAt(1, QColor(30, 120, 200))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(100, 200, 255), 2))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # Inner eye (sclera)
        inner_radius = radius - 8
        gradient = QRadialGradient(center_x - 2, center_y - 2, inner_radius)
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(200, 230, 255))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(150, 200, 255), 1))
        painter.drawEllipse(center_x - inner_radius, center_y - inner_radius, 
                           inner_radius * 2, inner_radius * 2)
        
        # Iris
        iris_radius = inner_radius - 5
        iris_x = center_x + int(self.pupil_offset * 5)
        iris_y = center_y + int(self.pupil_offset * 3)
        
        iris_gradient = QRadialGradient(iris_x - 3, iris_y - 3, iris_radius)
        iris_gradient.setColorAt(0, QColor(0, 100, 255))
        iris_gradient.setColorAt(1, QColor(0, 30, 100))
        painter.setBrush(QBrush(iris_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(iris_x - iris_radius, iris_y - iris_radius, 
                           iris_radius * 2, iris_radius * 2)
        
        # Pupil
        pupil_radius = iris_radius - 4
        pupil_x = iris_x + int(self.pupil_offset * 2)
        pupil_y = iris_y + int(self.pupil_offset)
        painter.setBrush(QColor(0, 0, 0))
        painter.drawEllipse(pupil_x - pupil_radius, pupil_y - pupil_radius,
                           pupil_radius * 2, pupil_radius * 2)
        
        # Highlight
        highlight_x = iris_x - 5
        highlight_y = iris_y - 5
        painter.setBrush(QColor(255, 255, 255, 180))
        painter.drawEllipse(highlight_x - 3, highlight_y - 3, 6, 6)
        
        # Scan line (robotic effect)
        if self.scan_line > 0:
            painter.setPen(QPen(QColor(0, 255, 255, 80), 2, Qt.DashLine))
            painter.drawLine(center_x - radius, center_y - radius + self.scan_line,
                            center_x + radius, center_y - radius + self.scan_line)


class CircularProgressBar(QLabel):
    """Animated circular progress bar"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.target_value = 0
        self.setMinimumSize(80, 80)
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(1000)
        self.anim.setEasingCurve(QEasingCurve.OutElastic)
        self.anim.valueChanged.connect(self.set_value)
        
    def set_target(self, value):
        self.anim.setStartValue(self.value)
        self.anim.setEndValue(value)
        self.anim.start()
        
    def set_value(self, value):
        self.value = value
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        center_x, center_y = w // 2, h // 2
        radius = min(w, h) // 2 - 10
        
        # Background circle
        painter.setPen(QPen(QColor(50, 100, 150, 100), 8))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # Progress arc
        if self.value > 0:
            painter.setPen(QPen(QColor(0, 200, 255), 10, Qt.SolidLine, Qt.RoundCap))
            span = int(360 * self.value / 100)
            painter.drawArc(center_x - radius, center_y - radius, radius * 2, radius * 2,
                           90 * 16, -span * 16)
        
        # Center text
        painter.setPen(QColor(200, 230, 255))
        font = QFont("Arial", 12, QFont.Bold)
        painter.setFont(font)
        painter.drawText(center_x - 20, center_y - 10, center_x + 20, center_y + 10,
                        Qt.AlignCenter, f"{int(self.value)}%")


class HolographicButton(QPushButton):
    """Holographic button with animation"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._hover_scale = 1.0
        self._glow_opacity = 0.0
        
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #b0f0ff;
                border: 2px solid #20a0ff;
                border-radius: 15px;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                color: white;
                border-color: #40f0ff;
            }
        """)
        
        # Shadow effect
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 200, 255, 100))
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)
        
    def enterEvent(self, event):
        self.anim_hover = QPropertyAnimation(self, b"hover_scale")
        self.anim_hover.setDuration(300)
        self.anim_hover.setStartValue(1.0)
        self.anim_hover.setEndValue(1.1)
        self.anim_hover.setEasingCurve(QEasingCurve.OutBounce)
        self.anim_hover.start()
        
        self.anim_glow = QPropertyAnimation(self, b"glow_opacity")
        self.anim_glow.setDuration(200)
        self.anim_glow.setStartValue(0)
        self.anim_glow.setEndValue(1)
        self.anim_glow.start()
        
    def leaveEvent(self, event):
        self.anim_hover = QPropertyAnimation(self, b"hover_scale")
        self.anim_hover.setDuration(300)
        self.anim_hover.setStartValue(1.1)
        self.anim_hover.setEndValue(1.0)
        self.anim_hover.start()
        
        self.anim_glow = QPropertyAnimation(self, b"glow_opacity")
        self.anim_glow.setStartValue(1)
        self.anim_glow.setEndValue(0)
        self.anim_glow.start()
        
    def get_hover_scale(self):
        return self._hover_scale
        
    def set_hover_scale(self, scale):
        self._hover_scale = float(scale)
        self.update()
        
    def get_glow_opacity(self):
        return self._glow_opacity
        
    def set_glow_opacity(self, opacity):
        self._glow_opacity = float(opacity)
        self.shadow.setBlurRadius(20 + int(self._glow_opacity * 20))
        self.shadow.setColor(QColor(0, 200, 255, int(100 + self._glow_opacity * 155)))
        
    hover_scale = pyqtProperty(float, get_hover_scale, set_hover_scale)
    glow_opacity = pyqtProperty(float, get_glow_opacity, set_glow_opacity)


class SentinelUI(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_queue = Queue()
        self.voice_started = False
        self.is_speaking = False
        self.mouth_toggle = False
        self._pulse_phase = 0
        self.particles = []
        
        # Futuristic window settings
        self.setWindowTitle("⚡ SENTINEL PRIME - AI ROBOT ASSISTANT ⚡")
        self.setGeometry(80, 30, 1400, 880)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        self._build_ui()
        self._setup_timers()
        self._setup_callbacks()
        self._initialize_camera()
        self._setup_advanced_animations()
        self._setup_particle_system()
        
        QTimer.singleShot(1300, self.start_voice)
        
    def _build_ui(self):
        # Main layout with margins for shadow effect
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title bar for frameless window
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)
        
        # Container for main content
        container = QFrame()
        container.setObjectName("mainContainer")
        container.setStyleSheet("""
            QFrame#mainContainer {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0a1a2f,
                    stop:0.3 #0d2a3f,
                    stop:0.7 #10384f,
                    stop:1 #0a2a3f
                );
                border: 2px solid qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #40a0ff,
                    stop:0.5 #80f0ff,
                    stop:1 #40a0ff
                );
                border-radius: 30px;
            }
        """)
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 150, 255, 160))
        shadow.setOffset(0, 0)
        container.setGraphicsEffect(shadow)
        
        root = QHBoxLayout(container)
        root.setSpacing(20)
        root.setContentsMargins(25, 25, 25, 25)
        
        # Left Panel
        self.left_panel = QFrame()
        self.left_panel.setObjectName("glassPanel")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setSpacing(15)
        
        # Robot eyes and header
        eyes_layout = QHBoxLayout()
        self.left_eye = AnimatedRobotEye()
        self.right_eye = AnimatedRobotEye()
        eyes_layout.addWidget(self.left_eye)
        eyes_layout.addWidget(self.right_eye)
        left_layout.addLayout(eyes_layout)
        
        self.header_label = QLabel("SENTINEL")
        self.header_label.setAlignment(Qt.AlignCenter)
        self.header_label.setStyleSheet("""
            font-size: 42px;
            font-weight: 900;
            font-family: 'Segoe UI', Arial;
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #40a0ff,
                stop:0.5 #80f0ff,
                stop:1 #40a0ff
            );
            background-clip: text;
            letter-spacing: 4px;
        """)
        left_layout.addWidget(self.header_label)
        
        # Status with circular progress
        status_layout = QHBoxLayout()
        self.status_label = QLabel("BOOTING")
        self.status_label.setStyleSheet("color: #80d0ff; font-size: 16px; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = CircularProgressBar()
        status_layout.addWidget(self.progress_bar)
        left_layout.addLayout(status_layout)
        
        # Clock and user info
        self.clock_label = QLabel("")
        self.clock_label.setStyleSheet("color: #a0e0ff; font-size: 14px; font-family: 'Courier New';")
        self.clock_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.clock_label)
        
        self.user_label = QLabel("USER: UNKNOWN")
        self.user_label.setStyleSheet("color: #60c0ff; font-size: 13px;")
        self.user_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.user_label)
        
        # Robot face with enhanced animation
        self.robot_face = QLabel("◉   ◉")
        self.robot_face.setAlignment(Qt.AlignCenter)
        self.robot_face.setStyleSheet("""
            font-size: 70px;
            color: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #40a0ff,
                stop:1 #80f0ff
            );
            font-weight: 900;
            background: rgba(0, 20, 40, 100);
            border-radius: 40px;
            padding: 20px;
        """)
        left_layout.addWidget(self.robot_face)
        
        self.robot_mouth = QLabel("═══  ═══")
        self.robot_mouth.setAlignment(Qt.AlignCenter)
        self.robot_mouth.setStyleSheet("""
            font-size: 35px;
            color: #40f0ff;
            letter-spacing: 8px;
            background: rgba(0, 30, 60, 150);
            border-radius: 20px;
            padding: 10px;
        """)
        left_layout.addWidget(self.robot_mouth)
        
        # Voice indicator with animation
        self.voice_indicator = QLabel("🎤 STANDBY")
        self.voice_indicator.setAlignment(Qt.AlignCenter)
        self.voice_indicator.setStyleSheet("""
            color: #80d0ff;
            font-size: 13px;
            border: 1px solid #40a0ff;
            border-radius: 15px;
            padding: 8px;
            background: rgba(0, 40, 80, 100);
        """)
        left_layout.addWidget(self.voice_indicator)
        
        # Vision stats with futuristic design
        vision_frame = QFrame()
        vision_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #3060a0;
                border-radius: 15px;
                background: rgba(0, 20, 40, 150);
                padding: 5px;
            }
        """)
        vision_layout = QVBoxLayout(vision_frame)
        
        self.vision_status_label = QLabel(f"🖥️ VISION: {get_vision_status()}")
        self.vision_status_label.setStyleSheet("color: #80d0ff;")
        vision_layout.addWidget(self.vision_status_label)
        
        stats_layout = QHBoxLayout()
        self.face_count_label = QLabel("👤 FACES: 0")
        self.face_count_label.setStyleSheet("color: #60ffa0;")
        stats_layout.addWidget(self.face_count_label)
        
        self.object_count_label = QLabel("📦 OBJECTS: 0")
        self.object_count_label.setStyleSheet("color: #ffa060;")
        stats_layout.addWidget(self.object_count_label)
        vision_layout.addLayout(stats_layout)
        
        left_layout.addWidget(vision_frame)
        
        # Chat with holographic style
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("✦ CONVERSATION LOG ✦")
        self.chat_history.setStyleSheet("""
            QTextEdit {
                background: rgba(5, 25, 45, 200);
                border: 2px solid #3060c0;
                border-radius: 20px;
                color: #d0f0ff;
                font-size: 13px;
                padding: 15px;
                selection-background-color: #4080ff;
            }
        """)
        left_layout.addWidget(self.chat_history)
        
        # Command input with futuristic style
        cmd_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("⚡ ENTER COMMAND ⚡")
        self.command_input.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 30, 60, 200);
                border: 2px solid #40a0ff;
                border-radius: 20px;
                color: white;
                font-size: 14px;
                padding: 12px 20px;
            }
            QLineEdit:focus {
                border: 2px solid #80f0ff;
                background: rgba(0, 40, 80, 220);
            }
        """)
        self.command_input.returnPressed.connect(self.on_send_clicked)
        cmd_layout.addWidget(self.command_input)
        
        self.send_btn = HolographicButton("⏎ SEND")
        self.send_btn.clicked.connect(self.on_send_clicked)
        cmd_layout.addWidget(self.send_btn)
        left_layout.addLayout(cmd_layout)
        
        # Right Panel
        self.right_panel = QFrame()
        self.right_panel.setObjectName("glassPanel")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setSpacing(15)
        
        # Camera with futuristic frame
        camera_frame = QFrame()
        camera_frame.setStyleSheet("""
            QFrame {
                border: 2px solid qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #40a0ff,
                    stop:1 #80f0ff
                );
                border-radius: 25px;
                background: rgba(0, 10, 20, 100);
            }
        """)
        camera_layout = QVBoxLayout(camera_frame)
        
        camera_header = QLabel("🔍 VISUAL FEED")
        camera_header.setAlignment(Qt.AlignCenter)
        camera_header.setStyleSheet("color: #80d0ff; font-size: 16px; font-weight: bold; padding: 5px;")
        camera_layout.addWidget(camera_header)
        
        self.camera_label = QLabel("INITIALIZING CAMERA...")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(750, 520)
        self.camera_label.setStyleSheet("""
            border: 1px solid #3060a0;
            border-radius: 20px;
            background: rgba(0, 20, 40, 150);
            color: #80a0ff;
            font-size: 18px;
        """)
        camera_layout.addWidget(self.camera_label)
        right_layout.addWidget(camera_frame)
        
        # Quick action buttons
        actions_label = QLabel("⚡ QUICK ACTIONS ⚡")
        actions_label.setAlignment(Qt.AlignCenter)
        actions_label.setStyleSheet("color: #80d0ff; font-size: 14px; padding: 5px;")
        right_layout.addWidget(actions_label)
        
        quick_row = QHBoxLayout()
        quick_actions = [
            ("📝 NOTEPAD", "open app notepad"),
            ("📋 LOGS", "read logs"),
            ("💬 CONVERSATION", "read conversation"),
            ("⏰ TIME", "what time is it"),
            ("📁 DIRECTORY", "run command dir"),
            ("👨 MALE", "__voice_male__"),
            ("👩 FEMALE", "__voice_female__"),
        ]
        
        for label, cmd in quick_actions:
            btn = HolographicButton(label)
            btn.clicked.connect(lambda _, x=cmd: self.send_command(x))
            quick_row.addWidget(btn)
        right_layout.addLayout(quick_row)
        
        # Detected objects with futuristic list
        objects_label = QLabel("📡 DETECTED OBJECTS")
        objects_label.setStyleSheet("color: #80d0ff; font-size: 14px;")
        right_layout.addWidget(objects_label)
        
        self.objects_list = QListWidget()
        self.objects_list.setStyleSheet("""
            QListWidget {
                background: rgba(0, 20, 40, 200);
                border: 2px solid #3060c0;
                border-radius: 15px;
                color: #d0f0ff;
                padding: 10px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #204080;
            }
            QListWidget::item:selected {
                background: #3060c0;
                border-radius: 8px;
            }
        """)
        self.objects_list.setMaximumHeight(120)
        right_layout.addWidget(self.objects_list)
        
        # Recent logs
        logs_label = QLabel("📜 SYSTEM LOGS")
        logs_label.setStyleSheet("color: #80d0ff; font-size: 14px;")
        right_layout.addWidget(logs_label)
        
        self.logs_list = QListWidget()
        self.logs_list.setStyleSheet("""
            QListWidget {
                background: rgba(0, 20, 40, 200);
                border: 2px solid #3060c0;
                border-radius: 15px;
                color: #a0e0ff;
                padding: 10px;
                font-size: 11px;
                font-family: 'Courier New';
            }
            QListWidget::item {
                padding: 3px;
                border-bottom: 1px solid #204080;
            }
        """)
        right_layout.addWidget(self.logs_list)
        
        # Set glass panel style
        for panel in [self.left_panel, self.right_panel]:
            panel.setStyleSheet("""
                QFrame#glassPanel {
                    background: rgba(10, 30, 50, 180);
                    border: 1px solid qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3060a0,
                        stop:1 #50a0c0
                    );
                    border-radius: 25px;
                }
            """)
        
        root.addWidget(self.left_panel, 2)
        root.addWidget(self.right_panel, 3)
        
        main_layout.addWidget(container)
        
    def _create_title_bar(self):
        """Create custom title bar for frameless window"""
        title_bar = QFrame()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        
        # Window title
        title_label = QLabel("⚡ SENTINEL PRIME v2.0 ⚡")
        title_label.setStyleSheet("""
            color: #80d0ff;
            font-size: 14px;
            font-weight: bold;
            font-family: 'Segoe UI';
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Window controls
        min_btn = QPushButton("─")
        max_btn = QPushButton("□")
        close_btn = QPushButton("✕")
        
        for btn in [min_btn, max_btn, close_btn]:
            btn.setFixedSize(30, 30)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0, 30, 60, 150);
                    color: #80d0ff;
                    border: 1px solid #3060a0;
                    border-radius: 5px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #3060c0;
                    color: white;
                }
            """)
            
        min_btn.clicked.connect(self.showMinimized)
        max_btn.clicked.connect(self.toggle_maximize)
        close_btn.clicked.connect(self.close)
        
        layout.addWidget(min_btn)
        layout.addWidget(max_btn)
        layout.addWidget(close_btn)
        
        return title_bar
        
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
            
    def _setup_advanced_animations(self):
        # Entry animations
        self.entry_group = QParallelAnimationGroup()
        
        # Left panel slide
        self.left_slide = QPropertyAnimation(self.left_panel, b"pos")
        self.left_slide.setDuration(800)
        self.left_slide.setStartValue(QPoint(-500, self.left_panel.y()))
        self.left_slide.setEndValue(QPoint(self.left_panel.x(), self.left_panel.y()))
        self.left_slide.setEasingCurve(QEasingCurve.OutBack)
        
        # Right panel slide
        self.right_slide = QPropertyAnimation(self.right_panel, b"pos")
        self.right_slide.setDuration(800)
        self.right_slide.setStartValue(QPoint(2000, self.right_panel.y()))
        self.right_slide.setEndValue(QPoint(self.right_panel.x(), self.right_panel.y()))
        self.right_slide.setEasingCurve(QEasingCurve.OutBack)
        
        # Title pulse
        self.title_pulse = QVariantAnimation(self)
        self.title_pulse.setDuration(2000)
        self.title_pulse.setLoopCount(-1)
        self.title_pulse.setStartValue(1.0)
        self.title_pulse.setEndValue(1.2)
        self.title_pulse.valueChanged.connect(self.pulse_title)
        self.title_pulse.setEasingCurve(QEasingCurve.InOutSine)
        
        self.entry_group.addAnimation(self.left_slide)
        self.entry_group.addAnimation(self.right_slide)
        
        QTimer.singleShot(100, self.entry_group.start)
        QTimer.singleShot(500, self.title_pulse.start)
        
    def _setup_particle_system(self):
        self.particle_timer = QTimer(self)
        self.particle_timer.timeout.connect(self.update_particles)
        self.particle_timer.start(50)
        
    def update_particles(self):
        # Simple particle effect
        if hasattr(self, 'camera_label'):
            self.camera_label.update()
            
    def pulse_title(self, value):
        self.header_label.setStyleSheet(f"""
            font-size: {int(42 * value)}px;
            font-weight: 900;
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #40a0ff,
                stop:0.5 #80f0ff,
                stop:1 #40a0ff
            );
            background-clip: text;
            letter-spacing: {int(4 * value)}px;
        """)
        
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
        self.mouth_timer.start(150)
        
        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.check_idle_thought)
        self.idle_timer.start(5000)
        
        self.eye_timer = QTimer(self)
        self.eye_timer.timeout.connect(self.animate_eyes)
        self.eye_timer.start(100)
        
    def _setup_callbacks(self):
        set_speaking_callback(lambda speaking: self.ui_queue.put(("speaking", speaking)))
        set_ui_reply_callback(lambda text: self.ui_queue.put(("reply", text)))
        self.update_clock()
        self.refresh_logs()
        
    def _initialize_camera(self):
        if not getattr(camera, "running", False):
            camera.start()
            
    def animate_eyes(self):
        # Animate robot eyes based on speaking and detection
        if hasattr(self, 'left_eye') and hasattr(self, 'right_eye'):
            # Pupil movement (follows mouse roughly)
            cursor = QCursor.pos()
            widget_pos = self.mapFromGlobal(cursor)
            
            # Calculate relative position
            rel_x = (widget_pos.x() - self.width()//2) / (self.width()//2)
            rel_y = (widget_pos.y() - self.height()//2) / (self.height()//2)
            
            # Limit movement
            rel_x = max(-1, min(1, rel_x))
            rel_y = max(-1, min(1, rel_y))
            
            self.left_eye.pupil_offset = rel_x * 2
            self.right_eye.pupil_offset = rel_x * 2
            
    def update_camera(self):
        self.vision_status_label.setText(f"🖥️ VISION: {get_vision_status()}")
        frame = camera.read()
        if frame is None:
            return
            
        frame, names = detect_faces(frame)
        self.face_count_label.setText(f"👤 FACES: {len(names)}")
        
        frame, objects = detect_objects(frame)
        unique_objects = sorted(set(objects))
        self.object_count_label.setText(f"📦 OBJECTS: {len(unique_objects)}")
        
        # Update progress bar based on object count
        progress = min(100, len(unique_objects) * 10)
        self.progress_bar.set_target(progress)
        
        self.objects_list.clear()
        for obj in unique_objects:
            self.objects_list.addItem(f"◉ {obj}")
            
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_image = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        
        # Add futuristic overlay
        pixmap = QPixmap.fromImage(qt_image)
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(0, 200, 255, 50), 2, Qt.DashLine))
        painter.drawRect(10, 10, w-20, h-20)
        painter.drawLine(10, 10, 30, 10)
        painter.drawLine(w-30, 10, w-10, 10)
        painter.drawLine(10, h-10, 30, h-10)
        painter.drawLine(w-30, h-10, w-10, h-10)
        painter.end()
        
        self.camera_label.setPixmap(pixmap)
        
    def append_chat(self, speaker, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        color = "#80f0ff" if speaker == "Sentinel" else "#ffa060"
        formatted = f'<span style="color: {color}; font-weight: bold;">[{stamp}] {speaker}:</span> {message}'
        self.chat_history.append(formatted)
        
    def send_command(self, text):
        command = text.strip()
        if not command:
            return
            
        if command == "__voice_male__":
            from ai_modules.voice_engine import set_voice
            set_voice(0)
            self.append_chat("System", "Switched to male voice.")
            speak("Voice switched to male.")
            return
            
        if command == "__voice_female__":
            from ai_modules.voice_engine import set_voice
            set_voice(1)
            self.append_chat("System", "Switched to female voice.")
            speak("Voice switched to female.")
            return
            
        self.append_chat("User", command)
        self.status_label.setText("⚡ PROCESSING ⚡")
        threading.Thread(target=self._run_command, args=(command,), daemon=True).start()
        
    def _run_command(self, command):
        process_command(command)
        self.ui_queue.put(("status", "🎤 LISTENING"))
        
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
                self.voice_indicator.setText("🎤 SPEAKING" if self.is_speaking else "🎤 LISTENING")
                if self.is_speaking:
                    self.voice_indicator.setStyleSheet("""
                        color: #80ffa0;
                        font-size: 13px;
                        border: 2px solid #80ffa0;
                        border-radius: 15px;
                        padding: 8px;
                        background: rgba(0, 80, 40, 100);
                    """)
                else:
                    self.voice_indicator.setStyleSheet("""
                        color: #80d0ff;
                        font-size: 13px;
                        border: 1px solid #40a0ff;
                        border-radius: 15px;
                        padding: 8px;
                        background: rgba(0, 40, 80, 100);
                    """)
                    
    def on_send_clicked(self):
        text = self.command_input.text()
        self.command_input.clear()
        self.send_command(text)
        
    def start_voice(self):
        if self.voice_started:
            return
        self.status_label.setText("🎤 LISTENING")
        Thread(target=listen_loop, args=(self.send_command,), daemon=True).start()
        self.voice_started = True
        self.progress_bar.set_target(100)
        
    def check_idle_thought(self):
        thought = idle_engine.check_idle()
        if thought:
            self.append_chat("Sentinel", thought)
            speak(thought)
            
    def animate_mouth(self):
        if not self.is_speaking:
            # Idle animation
            patterns = ["═══  ═══", "══    ══", "═      ═", "══    ══"]
            idx = (self._pulse_phase // 2) % len(patterns)
            self.robot_mouth.setText(patterns[idx])
            self._pulse_phase = (self._pulse_phase + 1) % 8
            return
            
        # Speaking animation
        patterns = [
            "◉═══  ═══◉",
            "◉══    ══◉",
            "◉═      ═◉",
            "◉══    ══◉",
            "◉═══  ═══◉",
            "◉════════◉",
        ]
        self.robot_mouth.setText(patterns[self._pulse_phase % len(patterns)])
        self._pulse_phase += 1
        
    def update_clock(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M:%S  |  %d %b %Y"))
        user_name = memory.get_current_user() or "UNKNOWN"
        self.user_label.setText(f"USER: {user_name.upper()}")
        
    def refresh_logs(self):
        logs = memory.get_logs()[-12:]
        self.logs_list.clear()
        for item in reversed(logs):
            time_str = item['time'] if 'time' in item else datetime.now().strftime("%H:%M:%S")
            event_str = item['event'][:40] + "..." if len(item['event']) > 40 else item['event']
            self.logs_list.addItem(f"⚡ {time_str} | {event_str}")
            
    def closeEvent(self, event):
        camera.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = SentinelUI()
    window.show()
    sys.exit(app.exec_())
