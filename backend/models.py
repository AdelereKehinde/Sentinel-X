from sqlalchemy import Column, Integer, String, Boolean, Text
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    face_encoding = Column(Text, nullable=True)


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    microphone = Column(Boolean, default=True)
    camera = Column(Boolean, default=True)
    memory = Column(Boolean, default=True)
    system_control = Column(Boolean, default=False)
    email_access = Column(Boolean, default=False)


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    response = Column(Text)