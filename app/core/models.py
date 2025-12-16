"""API-Modelle für das Secure AI Gateway: Eingangsnachrichten und
re-personalisierte Bot-Antworten."""
from pydantic import BaseModel


class UserMessage(BaseModel):
    """Eingehende Kundenanfrage inkl. Session-ID zur PII-Verknüpfung."""

    session_id: str
    message: str


class BotResponse(BaseModel):
    """Ausgehende Antwort des Gateways mit ursprünglicher Session-ID und Status."""

    session_id: str
    response: str
    status: str

