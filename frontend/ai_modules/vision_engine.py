import cv2
import torch
import face_recognition
import numpy as np
import time
from memory_engine import MemoryEngine
from ai_modules.autonomous_mode import controller
from backend.database import get_db

# Initialize Memory
memory = MemoryEngine()
db = next(get_db())
memory.load_users(db)

# Load YOLOv5 model (small version for speed)
model = torch.hub.load("ultralytics/yolov5", "yolov5n", pretrained=True)

# Camera
cap = cv2.VideoCapture(0)
last_greet_time = 0
GREET_DELAY = 10  # seconds

def recognize_faces(frame):
    global last_greet_time
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb)
    face_encodings = face_recognition.face_encodings(rgb, face_locations)

    names = []

    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(
            memory.known_face_encodings, face_encoding
        )
        name = "Unknown"

        if True in matches:
            match_index = matches.index(True)
            name = memory.known_face_names[match_index]

            if time.time() - last_greet_time > GREET_DELAY:
                print(f"Hello {name}, welcome back.")
                last_greet_time = time.time()
        else:
            # Register new user
            name = f"User{len(memory.known_face_names)+1}"
            memory.register_user(db, name, face_encoding)
            print(f"New user detected: {name}")

        names.append(name)

    return face_locations, names

def detect_objects(frame):
    results = model(frame)
    detections = results.pandas().xyxy[0]

    objects = []

    for _, row in detections.iterrows():
        label = row["name"]
        confidence = row["confidence"]

        if confidence > 0.5:
            objects.append(label)
            x1, y1, x2, y2 = int(row["xmin"]), int(row["ymin"]), int(row["xmax"]), int(row["ymax"])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return frame, objects

def start_vision():
    print("Sentinel vision activated.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Face recognition
        face_locations, names = recognize_faces(frame)
        for (top, right, bottom, left), name in zip(face_locations, names):
            cv2.rectangle(frame, (left, top), (right, bottom), (255, 0, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        # Object detection
        frame, objects = detect_objects(frame)
        if objects:
            unique_objects = list(set(objects))
            print("Detected objects:", unique_objects)

        # Show live camera feed
        cv2.imshow("Sentinel Vision", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    # Send data to autonomous robot brain
    controller.process_environment(objects, names)