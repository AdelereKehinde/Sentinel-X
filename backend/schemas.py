from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    face_encoding: str | None = None

class UserResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class SettingUpdate(BaseModel):
    microphone: bool
    camera: bool
    memory: bool
    system_control: bool
    email_access: bool

class LogCreate(BaseModel):
    action: str
    response: str