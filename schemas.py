"""
Database Schemas for broCoachme

Each Pydantic model below represents a MongoDB collection. The collection
name is the lowercase of the class name (e.g., Coach -> "coach").
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class Coach(BaseModel):
    name: Optional[str] = Field(None, description="Coach full name")
    email: EmailStr
    password: Optional[str] = Field(None, description="Hashed password or placeholder for MVP")
    avatar_url: Optional[str] = None

class Client(BaseModel):
    coach_id: str = Field(..., description="Owner coach id as string")
    name: str
    email: Optional[EmailStr] = None
    status: str = Field("Active", description="Active, Invited, In Progress")
    notes: Optional[str] = None
    last_activity: Optional[str] = None

class Invite(BaseModel):
    coach_id: str
    email: EmailStr
    message: Optional[str] = None
    status: str = Field("sent")

class Program(BaseModel):
    coach_id: str
    title: str
    description: Optional[str] = None
    sessions_count: int = 0

class Session(BaseModel):
    coach_id: str
    program_id: str
    title: str

class Exercise(BaseModel):
    coach_id: str
    session_id: str
    name: str
    sets: int
    reps: int
    rest_time: Optional[str] = None
    notes: Optional[str] = None
    video_url: Optional[str] = None

class Note(BaseModel):
    coach_id: str
    client_id: str
    content: str

class Activity(BaseModel):
    coach_id: str
    client_id: Optional[str] = None
    type: str = Field("info")
    message: str
    occurred_at: Optional[datetime] = None
