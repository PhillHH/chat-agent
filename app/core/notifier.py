"""Sendet Eskalationshinweise an MS Teams via Adaptive Card."""
import copy
from typing import List

import httpx

from app.core.config import settings

# Basis-Card mit Platzhaltern für Session und Verlauf.
BASE_ADAPTIVE_CARD = {
    "type": "message",
    "attachments": [
        {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": "Eskalation erforderlich"},
                    {"type": "TextBlock", "text": "Session ID: {session_id}", "wrap": True},
                    {"type": "TextBlock", "text": "Verlauf:", "wrap": True},
                    {"type": "TextBlock", "text": "{full_chat_history}", "wrap": True},
                ],
            },
        }
    ],
}


class TeamsNotifier:
    """Kapselt die Benachrichtigung an MS Teams bei Eskalationen."""

    def __init__(self) -> None:
        self.webhook_url = settings.teams_webhook_url

    async def notify_escalation(self, session_id: str, chat_history: List[str]) -> None:
        """Sendet eine Adaptive Card mit Session-ID und Chat-Verlauf an Teams."""
        if not self.webhook_url:
            return

        card_payload = copy.deepcopy(BASE_ADAPTIVE_CARD)
        joined_history = "\n".join(chat_history)
        card_payload["attachments"][0]["content"]["body"][1]["text"] = f"Session ID: {session_id}"
        card_payload["attachments"][0]["content"]["body"][3]["text"] = joined_history

        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json=card_payload)

