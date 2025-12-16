"""FastAPI-Einstiegspunkt für das Secure AI Gateway."""
import logging

from fastapi import FastAPI

from app.core.assistant import AIAssistant
from app.core.config import Settings
from app.core.database import get_redis_client
from app.core.logging_setup import setup_logging
from app.core.notifier import TeamsNotifier
from app.core.scanner import PIIScanner
from app.core.vault import PIIVault
from app.routers import chat as chat_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


# Initialisierung der App
app = FastAPI(
    title="Secure AI Gateway",
    version="1.0.0",
    description="Middleware for PII filtering and AI orchestration.",
)

# Setup Logging (File + Console)
setup_logging()
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("openai").setLevel(logging.INFO)

# Mount static files for the test frontend
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/test-chat", include_in_schema=False)
async def get_test_chat():
    return FileResponse("app/static/chat.html")


@app.on_event("startup")
def startup_event() -> None:
    """Initialisiert alle Services beim Start der Anwendung.

    - Prüft die Redis-Verbindung (Ping) beim Aufbau des Clients.
    - Lädt das GLiNER-Modell über den Scanner, damit spätere Requests warm sind.
    - Stellt sicher, dass die Logging-Konfiguration aktiv ist, um OpenAI-Aufrufe nachzuvollziehen.
    """
    # Settings laden
    settings = Settings()

    # Core Services initialisieren und im App State speichern
    # Redis Client
    redis_client = get_redis_client()
    app.state.vault = PIIVault(redis_client)

    # PII Scanner (hängt vom Vault ab)
    app.state.scanner = PIIScanner(app.state.vault)

    # AI Assistant (hängt von OpenAI Key ab)
    app.state.assistant = AIAssistant()

    # Notifier (hängt von Webhook URL ab)
    app.state.notifier = TeamsNotifier()

    print("🚀 Secure AI Gateway ist initialisiert.")


# Router registrieren
# Der Router wird als chat_router.router importiert
app.include_router(chat_router.router)

