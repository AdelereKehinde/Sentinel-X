# Sentinel
Sentinel is a local-first desktop AI assistant with a FastAPI brain service and a PyQt5 interface. It provides voice interaction, optional vision (YOLO or HOG fallback), memory utilities, and a system command layer designed for Windows.

---

## Screenshot (single slot)
Insert exactly one screenshot of the app here. Replace the file at `docs/screenshot.png` with your image.

![App Screenshot](docs/sentinel.png)

---

## Key Capabilities
- **Desktop UI (PyQt5):** A stylized assistant interface with animated elements and real-time status.
- **Voice I/O:** Offline-friendly TTS with optional speech recognition.
- **Vision:** Face detection + optional YOLO object detection, with HOG fallback.
- **Memory Engine:** Runtime-only memory for conversations and logs.
- **Backend Brain:** FastAPI endpoint that forwards prompts to OpenRouter.
- **System Control:** Basic local OS commands (open apps/folders, run terminal commands).

---

## Tech Stack
- **Frontend:** Python, PyQt5, OpenCV, SpeechRecognition, PyTTSx3
- **Backend:** FastAPI, SQLAlchemy, SQLite, Requests
- **AI Gateway:** OpenRouter API

---

## Repository Layout
```
sentinel/
  backend/
    main.py
    brain.py
    database.py
    models.py
    schemas.py
    requirements.txt
    .env
  frontend/
    runner/
      sentinel.py
    ui/
      sentinel_ui.py
      animations.py
    ai_modules/
      voice_engine.py
      vision_engine.py
      memory_engine.py
      system_control.py
      autonomous_mode.py
    models/
      yolo/
        yolo26n.pt
    requirements.txt
    .env
  README.md
```

---

## How It Works (High-Level)
1. **UI Launch:** `frontend/runner/sentinel.py` starts the PyQt5 UI.
2. **Voice Loop:** `voice_engine.py` listens, transcribes, and sends text to the backend.
3. **Brain Call:** Backend `/brain` endpoint forwards the prompt to OpenRouter.
4. **Response:** The UI speaks and displays the result.
5. **Vision (optional):** `vision_engine.py` runs face detection and object detection.
6. **Autonomy (optional):** `autonomous_mode.py` reacts to detected objects or faces.

---

## Quick Start

### 1. Backend Setup
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:
```
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
MAX_TOKENS=900
```

Run the API:
```powershell
uvicorn main:app --reload
```

### 2. Frontend Setup
```powershell
cd frontend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Optional `frontend/.env`:
```
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openai/gpt-4o-mini
MAX_TOKENS=900
```

Run the UI:
```powershell
python runner\sentinel.py
```

---

## Environment Variables
Backend (`backend/.env`):
- `OPENROUTER_API_KEY` (required)
- `OPENROUTER_MODEL` (default: `openai/gpt-4o-mini`)
- `MAX_TOKENS` (default: `900`)

Frontend (optional `frontend/.env`):
- `SR_ENERGY_THRESHOLD`
- `SR_PAUSE_THRESHOLD`
- `SR_NON_SPEAKING_DURATION`
- `VOICE_RATE`
- `VOICE_NAME`
- `MIC_INDEX`
- `ENABLE_HOG_FALLBACK`
- `HOG_INTERVAL`

---

## API Overview

### Brain
`POST /brain`
```json
{
  "input_text": "Hello"
}
```
Response:
```json
{
  "response": "Hi there...",
  "input_text": "Hello"
}
```

### Users
- `POST /users` creates or returns an existing user
- `GET /users` lists all users

### Settings
- `GET /settings` returns current toggles
- `PUT /settings` updates toggles

### Logs
- `POST /log` creates an action log

---

## Vision System
- **Face Detection:** OpenCV Haar cascade, fast and offline.
- **Object Detection:** YOLO if a local model exists.
- **Fallback:** Optional HOG-based people detection (CPU heavy).

To enable HOG fallback:
```
ENABLE_HOG_FALLBACK=1
HOG_INTERVAL=6
```

---

## Voice System
The voice engine uses `speech_recognition` for input and `pyttsx3` for output. It picks a reasonable Windows voice if available.

Useful options:
- `VOICE_NAME` to select a specific voice by name.
- `VOICE_RATE` to control speaking speed.
- `MIC_INDEX` to select a specific microphone.

---

## Memory Engine
The memory engine is runtime-only. It stores:
- Known users
- Logs
- Recent conversations

No disk writes occur from the memory engine.

---

## Troubleshooting
- **No voice input:** Ensure `pyaudio` is installed and your mic is selected via `MIC_INDEX`.
- **No vision:** Confirm your webcam works and `opencv-python` is installed.
- **YOLO missing:** Ensure the file exists at `frontend/models/yolo/yolo26n.pt`.
- **Backend errors:** Check `OPENROUTER_API_KEY` in `backend/.env`.

---

## Security Notes
- Do not commit `.env` files.
- The backend expects a local OpenRouter key.
- This project runs local OS commands; treat it as trusted-only.

---

## Roadmap Ideas
- Persist memory to a local encrypted store
- Add role-based settings and profiles
- Implement a plugin registry for new skills

---


