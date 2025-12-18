"""FastAPI-Einstiegspunkt für das Secure PolarisDX AI-Chat Gateway."""
import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.assistant import AIAssistant
from app.core.config import Settings
from app.core.database import get_redis_client
from app.core.logging_setup import setup_logging
from app.core.notifier import TeamsNotifier
from app.core.scanner import PIIScanner
from app.core.vault import PIIVault
from app.core.db_sqla import init_db

from app.routers import chat as chat_router
from app.routers import admin as admin_router
from app.routers import teams as teams_router


# Initialisierung der App
app = FastAPI(
    title="Secure PolarisDX AI-Chat Gateway",
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

@app.get("/test-chat-ws", include_in_schema=False)
async def get_test_chat_ws():
    return FileResponse("app/static/chat_v2.html")

# Admin Frontend Route (nur aktiv wenn Backend aktiv)
if os.getenv("ENABLE_ADMIN_BACKEND", "false").lower() == "true":
    @app.get("/admin-panel", include_in_schema=False)
    async def get_admin_panel():
        return FileResponse("app/static/admin.html")


@app.on_event("startup")
def startup_event() -> None:
    """Initialisiert alle Services beim Start der Anwendung.

    - Initialisiert SQLite Datenbank.
    - Prüft die Redis-Verbindung (Ping).
    - Lädt das GLiNER-Modell.
    """
    # Settings laden
    settings = Settings()

    # DB Initialisieren
    init_db()

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

    print("🚀 Secure PolarisDX AI-Chat Gateway ist initialisiert.")
    if os.getenv("ENABLE_ADMIN_BACKEND", "false").lower() == "true":
        print("✅ Admin Backend ist AKTIVIERT.")
    else:
        print("ℹ️ Admin Backend ist DEAKTIVIERT (Setze ENABLE_ADMIN_BACKEND=true zum Aktivieren).")


# Router registrieren
app.include_router(chat_router.router)
app.include_router(admin_router.router)
app.include_router(teams_router.router)
