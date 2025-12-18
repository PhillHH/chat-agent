"""Konfigurationsmodul für das Secure PolarisDX AI-Chat Gateway: lädt zentrale
Umgebungsvariablen (Redis, OpenAI, Ports) via Pydantic-Settings."""
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Hält alle konfigurierbaren Werte, die das Gateway zur Laufzeit
    benötigt (z.B. Redis-Endpunkt, API-Keys, Ports)."""

    redis_host: str = "redis"
    redis_port: int = 6379
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")  # Muss per Env gesetzt werden.
    assistant_id: str = Field("asst_YnzqT0bP0ag3mQ4O0v99HJiq", alias="ASSISTANT_ID")  # Im OpenAI-Dashboard generieren.
    teams_webhook_url: str = Field("", alias="TEAMS_WEBHOOK_URL")
    teams_app_id: str = Field("", alias="MICROSOFT_APP_ID")
    teams_app_password: str = Field("", alias="MICROSOFT_APP_PASSWORD")
    service_port: int = 1985


settings = Settings()

