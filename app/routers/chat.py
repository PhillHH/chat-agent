"""Chat-Router stellt den Hauptendpunkt des Secure AI Gateways bereit."""
from fastapi import APIRouter, HTTPException, Request, status

from app.core.models import BotResponse, UserMessage

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/message", response_model=BotResponse)
async def handle_message(message: UserMessage, request: Request) -> BotResponse:
    """Haupt-Endpunkt zur Verarbeitung von Kundenanfragen.

    Pipeline:
    1) Status-Check (Human Mode) via Vault-Status.
    2) PII-Filterung/Anonymisierung (Regex + GLiNER) über Scanner.
    3) KI-Aufruf (OpenAI Assistant) mit anonymisiertem Prompt.
    4) Entscheidung: Re-Personalisierung der Antwort oder Eskalation an Teams.
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
        anonymized_prompt = scanner.clean(message.message)
    except Exception as exc:  # pragma: no cover - defensive path
        # Fehler im Filter -> 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Filter service failed.",
        ) from exc

    # 3. AI Call (Assistant auf anonymisierten Prompt)
    ai_response, escalation = assistant.ask_assistant(session_id, anonymized_prompt)

    # 4. Entscheidung: Restore oder Eskalation
    if escalation:
        # Eskalation: Teams-Notify mit anonymisiertem Verlauf (MVP: letzter Prompt).
        await notifier.notify_escalation(
            session_id, chat_history=[f"Kundenfrage (anonymisiert): {anonymized_prompt}"]
        )
        vault.set_status(session_id, "HUMAN")
        return BotResponse(
            session_id=session_id,
            response="Ich konnte Ihnen nicht abschließend helfen. Ein Mitarbeiter wird in Kürze übernehmen.",
            status="ESCALATION_NEEDED",
        )

    final_response = scanner.restore(ai_response)
    return BotResponse(
        session_id=session_id,
        response=final_response,
        status="SUCCESS",
    )

