import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from database import db, create_document, get_documents

app = FastAPI(title="broCoachme API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Utility Models ----------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    success: bool
    coach_id: Optional[str] = None
    message: str

# ---------- Routes ----------
@app.get("/")
def root():
    return {"name": "broCoachme API", "status": "ok"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "❌ Unknown"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# ---- Auth (MVP mock) ----
@app.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    # MVP: accept any password and create/find a coach by email
    from schemas import Coach
    coach = {
        "email": payload.email,
        "name": payload.email.split("@")[0].title(),
    }
    # upsert-like behavior
    existing = db["coach"].find_one({"email": payload.email}) if db else None
    if existing:
        coach_id = str(existing.get("_id"))
    else:
        coach_id = create_document("coach", Coach(**coach))
    return LoginResponse(success=True, coach_id=coach_id, message="Logged in")

# ---- Dashboard overview ----
@app.get("/dashboard/summary")
async def dashboard_summary(coach_id: str):
    # totals
    total_clients = db["client"].count_documents({"coach_id": coach_id}) if db else 0
    recent_activity = list(db["activity"].find({"coach_id": coach_id}).sort("occurred_at", -1).limit(5)) if db else []
    for a in recent_activity:
        a["_id"] = str(a["_id"])  # make JSON serializable
    return {
        "total_clients": total_clients,
        "recent_activity": recent_activity,
        "quick_actions": ["Add Client", "Create Program"],
    }

# ---- Clients ----
class ClientCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    status: Optional[str] = "Active"
    notes: Optional[str] = None

@app.get("/clients")
async def list_clients(coach_id: str, q: Optional[str] = None):
    flt = {"coach_id": coach_id}
    if q:
        flt["name"] = {"$regex": q, "$options": "i"}
    clients = list(db["client"].find(flt).sort("_id", -1)) if db else []
    for c in clients:
        c["_id"] = str(c["_id"])  # stringify
    return clients

@app.post("/clients")
async def add_client(coach_id: str, payload: ClientCreate):
    from schemas import Client, Activity
    client_id = create_document("client", Client(coach_id=coach_id, **payload.model_dump()))
    create_document("activity", Activity(coach_id=coach_id, client_id=client_id, type="client", message=f"Added client {payload.name}", occurred_at=datetime.utcnow()))
    return {"success": True, "client_id": client_id}

# ---- Invites ----
class InviteRequest(BaseModel):
    email: EmailStr
    message: Optional[str] = None

@app.post("/invites")
async def send_invite(coach_id: str, payload: InviteRequest):
    from schemas import Invite, Activity
    invite_id = create_document("invite", Invite(coach_id=coach_id, email=payload.email, message=payload.message))
    create_document("activity", Activity(coach_id=coach_id, type="invite", message=f"Invite sent to {payload.email}", occurred_at=datetime.utcnow()))
    return {"success": True, "invite_id": invite_id}

# ---- Programs ----
class ProgramCreate(BaseModel):
    title: str
    description: Optional[str] = None

@app.get("/programs")
async def list_programs(coach_id: str):
    programs = list(db["program"].find({"coach_id": coach_id}).sort("_id", -1)) if db else []
    for p in programs:
        p["_id"] = str(p["_id"])
    return programs

@app.post("/programs")
async def create_program(coach_id: str, payload: ProgramCreate):
    from schemas import Program, Activity
    program_id = create_document("program", Program(coach_id=coach_id, title=payload.title, description=payload.description, sessions_count=0))
    create_document("activity", Activity(coach_id=coach_id, type="program", message=f"Created program {payload.title}", occurred_at=datetime.utcnow()))
    return {"success": True, "program_id": program_id}

@app.get("/programs/{program_id}")
async def get_program(program_id: str):
    prog = db["program"].find_one({"_id": {"$eq": __import__('bson').ObjectId(program_id)}})
    if not prog:
        raise HTTPException(status_code=404, detail="Program not found")
    prog["_id"] = str(prog["_id"])
    sessions = list(db["session"].find({"program_id": program_id}).sort("_id", 1))
    for s in sessions:
        s["_id"] = str(s["_id"])
    return {"program": prog, "sessions": sessions}

# ---- Sessions ----
class SessionCreate(BaseModel):
    title: str

@app.post("/programs/{program_id}/sessions")
async def add_session(coach_id: str, program_id: str, payload: SessionCreate):
    from schemas import Session
    session_id = create_document("session", Session(coach_id=coach_id, program_id=program_id, title=payload.title))
    # increment sessions_count
    db["program"].update_one({"_id": __import__('bson').ObjectId(program_id)}, {"$inc": {"sessions_count": 1}})
    return {"success": True, "session_id": session_id}

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    sess = db["session"].find_one({"_id": __import__('bson').ObjectId(session_id)})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    sess["_id"] = str(sess["_id"])
    exercises = list(db["exercise"].find({"session_id": session_id}).sort("_id", 1))
    for e in exercises:
        e["_id"] = str(e["_id"])
    return {"session": sess, "exercises": exercises}

# ---- Exercises ----
class ExerciseCreate(BaseModel):
    name: str
    sets: int
    reps: int
    rest_time: Optional[str] = None
    notes: Optional[str] = None
    video_url: Optional[str] = None

@app.post("/sessions/{session_id}/exercises")
async def add_exercise(coach_id: str, session_id: str, payload: ExerciseCreate):
    from schemas import Exercise
    exercise_id = create_document("exercise", Exercise(coach_id=coach_id, session_id=session_id, **payload.model_dump()))
    return {"success": True, "exercise_id": exercise_id}

# ---- Notes ----
class NoteCreate(BaseModel):
    client_id: str
    content: str

@app.post("/clients/{client_id}/notes")
async def add_note(coach_id: str, client_id: str, payload: NoteCreate):
    from schemas import Note
    if payload.client_id != client_id:
        raise HTTPException(status_code=400, detail="client_id mismatch")
    note_id = create_document("note", Note(coach_id=coach_id, client_id=client_id, content=payload.content))
    return {"success": True, "note_id": note_id}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
