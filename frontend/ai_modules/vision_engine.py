import os
import cv2
import time
import threading
from collections import deque

from ai_modules.autonomous_mode import controller

# ---------------- CONFIG ---------------- #
CONFIDENCE_THRESHOLD = 0.5
FPS_LIMIT = 10
CAMERA_INDEX = 0
YOLO_MODEL_NAME = "yolo26n.pt"  # your model

# Memory window for recent detections
DETECTION_MEMORY = deque(maxlen=30)

# ---------------------------------------- #

# Face detector (fast, offline)
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# YOLO setup (Ultralytics local)
YOLO_AVAILABLE = False
model = None
vision_status = "Offline mode (face + people)"

try:
    from ultralytics import YOLO

    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    FRONTEND_ROOT = os.path.dirname(ROOT_DIR)
    MODEL_PATH = os.path.join(FRONTEND_ROOT, "models", "yolo", YOLO_MODEL_NAME)

    if os.path.exists(MODEL_PATH):
        model = YOLO(MODEL_PATH)
        YOLO_AVAILABLE = True
        vision_status = f"YOLO active ({YOLO_MODEL_NAME})"
        print(f"[vision_engine] YOLO loaded from {MODEL_PATH}")
    else:
        print("[vision_engine] YOLO model not found, using fallback")

except Exception as e:
    print(f"[vision_engine] YOLO init failed: {e}")

# HOG fallback for people
hog = cv2.HOGDescriptor()
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


# -------- THREAD SAFE CAMERA -------- #
class CameraStream:
    def __init__(self, index=0):
        self.cap = cv2.VideoCapture(index)
        self.running = False
        self.frame = None
        self.lock = threading.Lock()

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self.update, daemon=True).start()

    def update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame

    def read(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.running = False
        self.cap.release()


camera = CameraStream(CAMERA_INDEX)


# -------- DETECTION FUNCTIONS -------- #
def detect_faces(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detections = face_cascade.detectMultiScale(gray, 1.2, 5)

    names = []
    for (x, y, w, h) in detections:
        names.append("Person")
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 80, 80), 2)
        cv2.putText(frame, "Person", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 80, 80), 2)

    return frame, names


def detect_with_yolo(frame):
    objects = []

    results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            label = model.names[cls]
            conf = float(box.conf[0])

            if conf < CONFIDENCE_THRESHOLD:
                continue

            objects.append(label)

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 80), 2)
            cv2.putText(
                frame,
                f"{label} {conf:.2f}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 200, 80),
                2,
            )

    return frame, objects


def detect_people_hog(frame):
    rects, _ = hog.detectMultiScale(frame, winStride=(8, 8))
    objects = []

    for (x, y, w, h) in rects:
        objects.append("person")
        cv2.rectangle(frame, (x, y), (x + w, y + h), (70, 170, 255), 2)
        cv2.putText(frame, "person", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (70, 170, 255), 2)

    return frame, objects


# -------- MAIN VISION LOOP -------- #
def start_vision():
    print("[vision_engine] Sentinel vision started")
    camera.start()

    last_time = 0

    try:
        while True:
            frame = camera.read()
            if frame is None:
                continue

            # FPS limiter
            if time.time() - last_time < 1 / FPS_LIMIT:
                continue
            last_time = time.time()

            # Face detection
            frame, names = detect_faces(frame)

            # Object detection
            if YOLO_AVAILABLE:
                frame, objects = detect_with_yolo(frame)
            else:
                frame, objects = detect_people_hog(frame)

            # Store short-term memory
            if objects or names:
                DETECTION_MEMORY.append({
                    "objects": list(set(objects)),
                    "faces": names,
                    "time": time.time()
                })

            # Display
            cv2.imshow("Sentinel Vision", frame)

            # Send environment snapshot to autonomous brain
            if len(DETECTION_MEMORY) >= 5:
                snapshot = DETECTION_MEMORY[-1]
                controller.process_environment(
                    snapshot["objects"],
                    snapshot["faces"]
                )

            # Exit key
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.stop()
        cv2.destroyAllWindows()
        print("[vision_engine] Vision stopped")


def detect_objects(frame):
    """
    Main detection function that uses YOLO if available, otherwise falls back to HOG.
    Returns: (processed_frame, list_of_objects)
    """
    if YOLO_AVAILABLE:
        return detect_with_yolo(frame)
    else:
        return detect_people_hog(frame)


def get_vision_status():
    return vision_status
