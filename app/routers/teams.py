"""Teams Bot Adapter und Router."""
from fastapi import APIRouter, Request, Response
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
    MemoryStorage,
    ConversationState,
    UserState
)
from botbuilder.schema import Activity, ActivityTypes
from app.core.config import settings
from app.core.connection_manager import manager
import logging
import asyncio
import re

router = APIRouter(prefix="/api/messages", tags=["Teams Bot"])
logger = logging.getLogger(__name__)

# Konfiguration des Bot Framework Adapters
# In Production sollten APP_ID und APP_PASSWORD aus den Settings kommen.
# Für den lokalen Test oder wenn nicht konfiguriert, kann es leer bleiben (aber Auth schlägt fehl wenn Teams anfragt).
ADAPTER_SETTINGS = BotFrameworkAdapterSettings(
    app_id=settings.teams_app_id if hasattr(settings, "teams_app_id") else "",
    app_password=settings.teams_app_password if hasattr(settings, "teams_app_password") else ""
)

ADAPTER = BotFrameworkAdapter(ADAPTER_SETTINGS)

# State Management (Optional, aber gut für Kontext)
MEMORY = MemoryStorage()
CONVERSATION_STATE = ConversationState(MEMORY)

async def bot_logic(turn_context: TurnContext):
    """Die Hauptlogik für eingehende Teams-Nachrichten."""

    # Eingehende Nachricht vom Mitarbeiter in Teams
    if turn_context.activity.type == ActivityTypes.message:
        text = turn_context.activity.text.strip()
        conversation_id = turn_context.activity.conversation.id

        # Check for connection command: "connect <session_id>"
        # Regex to match "connect sess_..." case insensitive
        match = re.search(r"connect\s+(sess_[a-zA-Z0-9]+)", text, re.IGNORECASE)

        if match:
            session_id_to_connect = match.group(1)
            # Store the reference
            manager.set_teams_reference(session_id_to_connect, turn_context.activity.get_conversation_reference())
            await turn_context.send_activity(f"✅ Verbunden mit Session: {session_id_to_connect}. Sie können jetzt chatten.")

            # Notify User via WebSocket
            import json
            await manager.send_personal_message(json.dumps({
                "type": "system",
                "text": "Ein Mitarbeiter ist dem Chat beigetreten."
            }), session_id_to_connect)
            return

        # 1. Versuche, die zugehörige Web-Session zu finden
        session_id = manager.get_session_by_conversation(conversation_id)

        if session_id:
            logger.info(f"Received from Teams for session {session_id}: {text}")
            # 2. Sende die Nachricht an das Frontend via WebSocket
            # Formatieren als JSON, damit das Frontend weiß, dass es vom Agenten kommt
            import json
            payload = json.dumps({
                "type": "agent_message",
                "text": text,
                "sender": "Agent"
            })
            await manager.send_personal_message(payload, session_id)
        else:
            # Fallback: Wenn wir nicht wissen, zu wem das gehört
            await turn_context.send_activity("⚠️ Nicht verbunden. Bitte antworten Sie mit 'connect <session_id>', um einen Chat zu übernehmen.")

    elif turn_context.activity.type == ActivityTypes.conversation_update:
        # Wenn der Bot hinzugefügt wird
        pass

@router.post("")
async def messages(request: Request):
    """Endpunkt für Nachrichten vom Azure Bot Service."""
    if "application/json" in request.headers["content-type"]:
        body = await request.json()
    else:
        return Response(status_code=415)

    activity = Activity().deserialize(body)

    auth_header = request.headers.get("Authorization", "")

    try:
        response = await ADAPTER.process_activity(activity, auth_header, bot_logic)
        if response:
            return response
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error processing Teams activity: {e}")
        return Response(status_code=500)
