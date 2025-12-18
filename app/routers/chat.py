"""Chat-Router stellt den Hauptendpunkt des Secure PolarisDX AI-Chat Gateways bereit."""
from fastapi import APIRouter, HTTPException, Request, status, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import asyncio
import logging
import json

from app.core.models import BotResponse, UserMessage
from app.core.db_sqla import SessionLocal, ChatSession, ChatMessage
from app.core.connection_manager import manager
from app.routers.teams import ADAPTER

# Import botbuilder types for proactive messaging
from botbuilder.schema import Activity, ActivityTypes, ConversationReference
from botbuilder.core import TurnContext

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)

def save_user_message_sync(session_id: str, message_text: str):
    """Speichert die User-Nachricht synchron in einem Thread."""
    db = SessionLocal()
    try:
        # Check if session exists
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            session = ChatSession(id=session_id)
            db.add(session)
            db.commit() # Commit session creation first

        msg = ChatMessage(session_id=session_id, role="user", content=message_text)
        db.add(msg)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save user message for session {session_id}: {e}")
    finally:
        db.close()

def save_bot_message_sync(session_id: str, message_text: str):
    """Speichert die Bot-Nachricht synchron in einem Thread."""
    db = SessionLocal()
    try:
        # Session should exist from user message, but safety check
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            session = ChatSession(id=session_id)
            db.add(session)
            db.commit()

        msg = ChatMessage(session_id=session_id, role="assistant", content=message_text)
        db.add(msg)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save bot message for session {session_id}: {e}")
    finally:
        db.close()

# Helper function to send message to Teams (Proactive)
async def send_to_teams(session_id: str, text: str, role: str):
    reference = manager.get_teams_reference(session_id)
    if not reference:
        return

    async def callback(turn_context: TurnContext):
        prefix = "[KUNDE]" if role == "user" else "[BOT]"
        await turn_context.send_activity(f"{prefix} {text}")

    try:
        # We need to recreate the reference object carefully or use it directly
        # ADAPTER.continue_conversation requires arguments in a specific way
        await ADAPTER.continue_conversation(reference, callback, app_id=ADAPTER._settings.app_id)
    except Exception as e:
        logger.error(f"Failed to send to Teams: {e}")


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)

    # Access services from app state
    # Note: In WebSocket, request.app is available via websocket.app
    vault = websocket.app.state.vault
    scanner = websocket.app.state.scanner
    assistant = websocket.app.state.assistant
    notifier = websocket.app.state.notifier

    try:
        while True:
            data = await websocket.receive_text()
            # Parse JSON if possible, otherwise treat as raw text
            try:
                message_data = json.loads(data)
                user_text = message_data.get("message", "")
            except:
                user_text = data

            if not user_text:
                continue

            # -- DB LOGGING --
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, save_user_message_sync, session_id, user_text)
            except Exception as e:
                logger.error(f"Failed to async save user message: {e}")

            # Send to Teams (Monitor)
            await send_to_teams(session_id, user_text, "user")

            # 1. Human Mode Check
            if vault.get_status(session_id) == "HUMAN":
                await manager.send_personal_message(json.dumps({
                    "type": "system",
                    "text": "Weiterleitung an Mitarbeiter...",
                    "status": "HUMAN_MODE"
                }), session_id)
                # Here we expect the agent to reply via Teams (handled in teams.py)
                continue

            # 2. PII Filterung
            try:
                anonymized_prompt = await scanner.clean(user_text)
            except Exception as e:
                await manager.send_personal_message(json.dumps({"type": "error", "text": "Filter Error"}), session_id)
                continue

            # 3. AI Stream
            full_text_accumulator = []
            full_restored_accumulator = []

            # Send initial "start" message if needed
            # await manager.send_personal_message(json.dumps({"type": "start"}), session_id)

            ai_stream = assistant.ask_assistant_stream(session_id, anonymized_prompt)

            async for restored_chunk in scanner.restore_stream(ai_stream):
                 # Check/Remove Escalation Token
                if "ESKALATION_NOETIG" in restored_chunk:
                    restored_chunk = restored_chunk.replace("ESKALATION_NOETIG", "")
                    full_text_accumulator.append("ESKALATION_NOETIG") # Mark for later

                if restored_chunk:
                    full_restored_accumulator.append(restored_chunk)
                    # Stream to WS
                    await manager.send_personal_message(json.dumps({
                        "type": "chunk",
                        "text": restored_chunk
                    }), session_id)

            final_bot_text = "".join(full_restored_accumulator)

            # Send "done" message
            await manager.send_personal_message(json.dumps({"type": "done"}), session_id)

            # DB Log Bot
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, save_bot_message_sync, session_id, final_bot_text)
            except Exception as e:
                logger.error(f"Failed to async save bot response: {e}")

            # Send to Teams (Monitor)
            await send_to_teams(session_id, final_bot_text, "assistant")

            # Check Escalation
            if "ESKALATION_NOETIG" in "".join(full_text_accumulator):
                 full_history = await assistant.get_thread_history(session_id)
                 if not full_history:
                    full_history = [f"Kundenfrage (anonymisiert): {anonymized_prompt}"]

                 # Notify Teams (Old Webhook way OR Bot way if we had a conversation ref)
                 # If we don't have a conversation ref yet, we use the old webhook to notify
                 if not manager.get_teams_reference(session_id):
                     # Add instruction how to connect
                     full_history.append(f"\n[SYSTEM] Um diesen Chat zu übernehmen, antworten Sie dem Bot mit: connect {session_id}")
                     await notifier.notify_escalation(session_id, chat_history=full_history)

                 vault.set_status(session_id, "HUMAN")
                 await manager.send_personal_message(json.dumps({
                     "type": "system",
                     "text": "Ein Mitarbeiter übernimmt.",
                     "status": "ESKALATION"
                 }), session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(session_id)


@router.post("/message", response_model=BotResponse)
async def handle_message(message: UserMessage, request: Request):
    """Haupt-Endpunkt zur Verarbeitung von Kundenanfragen.

    Pipeline:
    1) Status-Check (Human Mode) via Vault-Status.
    2) PII-Filterung/Anonymisierung (Regex + GLiNER) über Scanner.
    3) KI-Aufruf (OpenAI Assistant) mit anonymisiertem Prompt (Streaming).
    4) Entscheidung: Re-Personalisierung der Antwort (Streaming) oder Eskalation an Teams.
    """
    vault = request.app.state.vault
    scanner = request.app.state.scanner
    assistant = request.app.state.assistant
    notifier = request.app.state.notifier
    session_id = message.session_id

    # -- DB LOGGING START --
    # User-Nachricht SOFORT speichern (via ThreadPool), damit die Reihenfolge stimmt.
    # BackgroundTasks würden erst NACH dem Response laufen, was zu Timestamp-Inversion führt.
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, save_user_message_sync, session_id, message.message)
    except Exception as e:
        logger.error(f"Failed to async save user message: {e}")
    # -- DB LOGGING END --

    # Monitor in Teams (if connection exists)
    await send_to_teams(session_id, message.message, "user")

    # 1. Human Mode Check
    if vault.get_status(session_id) == "HUMAN":
        return BotResponse(
            session_id=session_id,
            response="Ein menschlicher Mitarbeiter hat die Konversation übernommen. Bitte warten Sie auf eine Antwort.",
            status="HUMAN_MODE",
        )

    # 2. PII Filterung (Anonymisierung: DSGVO-Schritt)
    try:
        anonymized_prompt = await scanner.clean(message.message)
    except Exception as exc:  # pragma: no cover - defensive path
        # Fehler im Filter -> 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Filter service failed.",
        ) from exc

    # 3. & 4. AI Call & Restore (Streaming)

    # Eskalations-Erkennung "Out-of-band" via Accumulator
    full_text_accumulator = []

    # Sammelt den finalen, re-personalisierten Text für die DB
    full_restored_accumulator = []

    async def stream_generator():
        # Hole den AI Stream (Yields Tokens)
        ai_stream = assistant.ask_assistant_stream(session_id, anonymized_prompt)

        # Leite AI Stream durch PII Restorer (Yields Restored Tokens)
        # Und sammle rohen Text für Eskalations-Check

        async def tee_generator(original_gen):
            async for chunk in original_gen:
                full_text_accumulator.append(chunk)
                yield chunk

        # PII Restore Stream
        # Filter "ESKALATION_NOETIG" logic within the stream
        async for clean_chunk in scanner.restore_stream(tee_generator(ai_stream)):
            # Remove/Hide internal escalation token if it leaks into the stream
            if "ESKALATION_NOETIG" in clean_chunk:
                clean_chunk = clean_chunk.replace("ESKALATION_NOETIG", "")

            if clean_chunk:
                full_restored_accumulator.append(clean_chunk)
                yield clean_chunk

        # Nachdem der Stream fertig ist, prüfen wir auf Eskalation
        full_text = "".join(full_text_accumulator)

        # -- DB LOGGING START --
        # Bot-Antwort speichern.
        final_bot_text = "".join(full_restored_accumulator)
        try:
             loop = asyncio.get_running_loop()
             await loop.run_in_executor(None, save_bot_message_sync, session_id, final_bot_text)
        except Exception as e:
             logger.error(f"Failed to async save bot response: {e}")
        # -- DB LOGGING END --

        # Monitor in Teams
        await send_to_teams(session_id, final_bot_text, "assistant")

        if "ESKALATION_NOETIG" in full_text:
             # Eskalation auslösen
             full_history = await assistant.get_thread_history(session_id)
             if not full_history:
                full_history = [f"Kundenfrage (anonymisiert): {anonymized_prompt}"]

             await notifier.notify_escalation(
                session_id, chat_history=full_history
             )
             vault.set_status(session_id, "HUMAN")

             # Inform the user in the stream
             yield "\n\n⚠️ Ein Mitarbeiter wird in Kürze übernehmen (Eskalation ausgelöst)."

    return StreamingResponse(stream_generator(), media_type="text/plain")
