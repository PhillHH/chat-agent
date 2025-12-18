"""Admin-Router für das Verwaltungsbackend (TrainingsHub)."""
import os
import csv
import io
import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.db_sqla import get_db, ChatSession, ChatMessage

# Environment Variable prüfen, ob Admin Backend aktiv ist
ADMIN_ENABLED = os.getenv("ENABLE_ADMIN_BACKEND", "false").lower() == "true"

router = APIRouter(prefix="/admin", tags=["Admin"])

# Pydantic Modelle für Responses
class MessageRead(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

class SessionRead(BaseModel):
    id: str
    created_at: datetime.datetime
    notes: Optional[str] = None
    # Wir laden messages nur in Detailansicht, um Liste klein zu halten

    class Config:
        from_attributes = True

class SessionDetail(SessionRead):
    messages: List[MessageRead] = []

class NoteUpdate(BaseModel):
    notes: str


@router.get("/sessions", response_model=List[SessionRead])
def list_sessions(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """Listet alle Chat-Sessions auf."""
    if not ADMIN_ENABLED:
        raise HTTPException(status_code=403, detail="Admin backend disabled")

    sessions = db.query(ChatSession).order_by(ChatSession.created_at.desc()).offset(skip).limit(limit).all()
    return sessions

@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session_details(session_id: str, db: Session = Depends(get_db)):
    """Zeigt Details und Nachrichten einer Session."""
    if not ADMIN_ENABLED:
        raise HTTPException(status_code=403, detail="Admin backend disabled")

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/sessions/{session_id}/note", response_model=SessionRead)
def update_session_note(session_id: str, note_data: NoteUpdate, db: Session = Depends(get_db)):
    """Aktualisiert die Notizen zu einer Session."""
    if not ADMIN_ENABLED:
        raise HTTPException(status_code=403, detail="Admin backend disabled")

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.notes = note_data.notes
    db.commit()
    db.refresh(session)
    return session

@router.get("/export")
def export_data(db: Session = Depends(get_db)):
    """Exportiert alle Sessions und Nachrichten als CSV."""
    if not ADMIN_ENABLED:
        raise HTTPException(status_code=403, detail="Admin backend disabled")

    # CSV Generator
    def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["session_id", "session_created_at", "session_notes", "message_role", "message_time", "message_content"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Daten query (könnte bei sehr vielen Daten Memory Probleme machen, hier für 'small' ok)
        sessions = db.query(ChatSession).all()
        for s in sessions:
            for m in s.messages:
                writer.writerow([
                    s.id,
                    s.created_at.isoformat(),
                    s.notes or "",
                    m.role,
                    m.timestamp.isoformat(),
                    m.content
                ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

    return StreamingResponse(iter_csv(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=training_data.csv"})
