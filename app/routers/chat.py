"""Chat-Router stellt den Hauptendpunkt des Secure PolarisDX AI-Chat Gateways bereit."""
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
import asyncio

from app.core.models import BotResponse, UserMessage

router = APIRouter(prefix="/chat", tags=["Chat"])


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

    async def stream_generator():
        # Hole den AI Stream (Yields Tokens)
        ai_stream = assistant.ask_assistant_stream(session_id, anonymized_prompt)

        # Leite AI Stream durch PII Restorer (Yields Restored Tokens)
        # Und sammle rohen Text für Eskalations-Check

        # Da `ask_assistant_stream` ein Generator ist, können wir ihn direkt iterieren.
        # Aber wir wollen auch den rohen Text sammeln.
        # Problem: `restore_stream` konsumiert den Generator.
        # Wir müssen uns dazwischen hängen ("Tee").

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
                yield clean_chunk

        # Nachdem der Stream fertig ist, prüfen wir auf Eskalation
        full_text = "".join(full_text_accumulator)
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
