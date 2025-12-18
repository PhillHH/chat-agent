"""Connection Manager für WebSocket-Verbindungen und Teams-Konversationen."""
from typing import Dict, Optional, List
from fastapi import WebSocket
from botbuilder.schema import ConversationReference
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Verwaltet aktive WebSocket-Verbindungen und deren Zuordnung zu Teams-Konversationen."""

    def __init__(self):
        # Mappt session_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Mappt session_id -> ConversationReference (für Teams)
        self.teams_references: Dict[str, ConversationReference] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """Nimmt eine neue WebSocket-Verbindung an."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")

    def disconnect(self, session_id: str):
        """Entfernt eine WebSocket-Verbindung."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")

    def set_teams_reference(self, session_id: str, reference: ConversationReference):
        """Speichert die Teams-Referenz für eine Session."""
        self.teams_references[session_id] = reference
        logger.info(f"Teams reference set for: {session_id}")

    def get_teams_reference(self, session_id: str) -> Optional[ConversationReference]:
        """Holt die Teams-Referenz für eine Session."""
        return self.teams_references.get(session_id)

    def get_session_by_conversation(self, conversation_id: str) -> Optional[str]:
        """Findet eine Session-ID basierend auf der Teams Conversation ID.
        Dies ist eine einfache Implementierung. In Production sollte dies robust
        über eine DB gelöst werden, wenn References persistiert werden müssen.
        """
        for session_id, ref in self.teams_references.items():
            if ref.conversation.id == conversation_id:
                return session_id
        return None

    async def send_personal_message(self, message: str, session_id: str):
        """Sendet eine Nachricht an einen spezifischen WebSocket-Client."""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(message)
            except Exception as e:
                logger.error(f"Error sending to WS {session_id}: {e}")
                self.disconnect(session_id)
        else:
            logger.warning(f"No active WebSocket connection for {session_id}")

    async def broadcast(self, message: str):
        """Sendet an alle (nur für Debugging sinnvoll)."""
        for connection in self.active_connections.values():
            await connection.send_text(message)

# Globaler Manager
manager = ConnectionManager()
