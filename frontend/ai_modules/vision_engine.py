import os
import cv2
import numpy as np

from ai_modules.autonomous_mode import controller

cap = cv2.VideoCapture(0)
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT_DIR)
MODEL_DIRS = [
    os.path.join(ROOT_DIR, "models", "yolo"),
    os.path.join(PROJECT_ROOT, "backend", "models", "yolo"),
]

# torch is optional – a failed DLL load or missing package must not crash us.
try:
    import torch
    TORCH_AVAILABLE = True
except Exception as exc:
    print(f"[vision_engine] warning – torch import failed: {exc}")
    TORCH_AVAILABLE = False

model = None
vision_status = "Face + people detection (offline)"

# Offline fallback: no download required, detects people only.
hog = cv2.HOGDescriptor()
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


def _find_yolo_pt_file():
    """Search for yolov5n.pt in model directories."""
    for model_dir in MODEL_DIRS:
        pt_path = os.path.join(model_dir, "yolov5n.pt")
        if os.path.exists(pt_path):
            return pt_path
    return None


def _load_yolo():
    global model, vision_status
    if not TORCH_AVAILABLE:
        print("[vision_engine] torch not available – skipping YOLO")
        return

    try:
        pt_file = _find_yolo_pt_file()
        if not pt_file:
            raise FileNotFoundError(
                "yolov5n.pt not found. Place yolov5n.pt in "
                "frontend/models/yolo or backend/models/yolo."
            )

        print(f"[vision_engine] Loading YOLO from {pt_file}")
        model = torch.hub.load("ultralytics/yolov5", "custom", path=pt_file)
        vision_status = "YOLO active (YOLOv5)"
        print("[vision_engine] YOLO loaded successfully (yolov5n.pt).")
    except Exception as exc:
        model = None
        vision_status = f"Face + people detection (offline) | YOLO unavailable: {exc}"
        print(f"[vision_engine] warning - YOLO unavailable: {exc}")


_load_yolo()


def get_vision_status():
    return vision_status


def recognize_faces(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detections = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40)
    )

    face_locations = []
    names = []
    for (x, y, w, h) in detections:
        top, right, bottom, left = y, x + w, y + h, x
        face_locations.append((top, right, bottom, left))
        names.append("Person")

    return face_locations, names


def _detect_with_yolo(frame):
    """Detect objects using YOLOv5 model."""
    results = model(frame)
    detections = results.pandas().xyxy[0]
    
    objects = []
    for _, row in detections.iterrows():
        label = row["name"]
        confidence = row["confidence"]
        
        if confidence > 0.5:
            objects.append(label)
            x1 = int(row["xmin"])
            y1 = int(row["ymin"])
            x2 = int(row["xmax"])
            y2 = int(row["ymax"])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 80), 2)
            cv2.putText(
                frame,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 200, 80),
                2,
            )
    
    return frame, objects


def _detect_people_offline(frame):
    """Fallback: detect people using HOG descriptor."""
    rects, _ = hog.detectMultiScale(
        frame, winStride=(8, 8), padding=(8, 8), scale=1.05
    )
    objects = []
    for (x, y, w, h) in rects:
        objects.append("person")
        cv2.rectangle(frame, (x, y), (x + w, y + h), (70, 170, 255), 2)
        cv2.putText(
            frame,
            "person",
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (70, 170, 255),
            2,
        )
    return frame, objects


def detect_objects(frame):
    """Detect objects using YOLO or fallback to offline people detection."""
    if model is not None:
        try:
            return _detect_with_yolo(frame)
        except Exception as exc:
            print(f"[vision_engine] warning - YOLO inference failed, using fallback: {exc}")
    return _detect_people_offline(frame)


def start_vision():
    print("Sentinel vision activated.")
    last_objects = []
    last_names = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        face_locations, names = recognize_faces(frame)
        for (top, right, bottom, left), name in zip(face_locations, names):
            cv2.rectangle(frame, (left, top), (right, bottom), (255, 80, 80), 2)
            cv2.putText(
                frame,
                name,
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 80, 80),
                2,
            )

        frame, objects = detect_objects(frame)
        if objects:
            last_objects = list(set(objects))
        if names:
            last_names = names

        cv2.imshow("Sentinel Vision", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    controller.process_environment(last_objects, last_names)