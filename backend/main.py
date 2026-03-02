from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import Base, engine, get_db
import models, schemas
from brain import ask_brain

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sentinel Prime Brain")


class BrainRequest(BaseModel):
    input_text: str | None = None
    message: str | None = None

# Initialize default settings
@app.on_event("startup")
def startup():
    db = next(get_db())
    settings = db.query(models.Setting).first()
    if not settings:
        default_settings = models.Setting()
        db.add(default_settings)
        db.commit()

# ------------------- USERS -------------------
@app.post("/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.name == user.name).first()
    if existing:
        return existing
    new_user = models.User(name=user.name, face_encoding=user.face_encoding)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

# ------------------- SETTINGS -------------------
@app.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return db.query(models.Setting).first()

@app.put("/settings")
def update_settings(settings: schemas.SettingUpdate, db: Session = Depends(get_db)):
    current = db.query(models.Setting).first()
    for key, value in settings.dict().items():
        setattr(current, key, value)
    db.commit()
    return {"message": "Settings updated"}

# ------------------- LOGS -------------------
@app.post("/log")
def create_log(log: schemas.LogCreate, db: Session = Depends(get_db)):
    new_log = models.Log(action=log.action, response=log.response)
    db.add(new_log)
    db.commit()
    return {"message": "Logged"}

# ------------------- BRAIN -------------------
@app.post("/brain")
def brain(
    input_text: str | None = None,
    payload: BrainRequest | None = None,
    db: Session = Depends(get_db),
):
    text = input_text
    if payload is not None:
        text = payload.input_text or payload.message or text

    if not text:
        raise HTTPException(status_code=422, detail="input_text or message is required")

    try:
        response = ask_brain(text)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"response": response}
