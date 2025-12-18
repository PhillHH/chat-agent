"""Datenbankmodelle für die persistente Speicherung von Chat-Verläufen (TrainingsHub)."""
import datetime
from typing import List, Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from app.core.config import settings

# Basis-Klasse für SQLAlchemy Modelle
class Base(DeclarativeBase):
    pass

class ChatSession(Base):
    """Repräsentiert eine Chat-Sitzung."""
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Wir nutzen die session_id vom Client/System
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    # Notizen für das Admin-Backend (z.B. zur Bewertung oder Analyse)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Beziehung zu Nachrichten
    messages: Mapped[List["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatSession(id='{self.id}', created_at='{self.created_at}')>"


class ChatMessage(Base):
    """Repräsentiert eine einzelne Nachricht innerhalb einer Session."""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"))

    role: Mapped[str] = mapped_column(String(50))  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(Text)     # Der eigentliche Text (ggf. re-personalisiert für Lesbarkeit)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(role='{self.role}', session_id='{self.session_id}')>"


# SQLite Datenbank Setup
# Wir nutzen eine lokale Datei `training_hub.db`
DB_URL = "sqlite:///./training_hub.db"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Erstellt die Tabellen, falls sie noch nicht existieren."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency für FastAPI Routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
