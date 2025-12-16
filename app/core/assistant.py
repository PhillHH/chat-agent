"""Steuert die Kommunikation mit der OpenAI Assistant API inkl.
Eskalationslogik für das Secure PolarisDX AI-Chat Gateway."""
import os
import asyncio
import logging
from typing import Dict, Tuple, List

from openai import AsyncOpenAI

from app.core.config import settings

# Platzhalter-Assistent; kann über Settings/Env überschrieben werden.
ASSISTANT_ID = settings.assistant_id


class AIAssistant:
    """Sendet bereinigte Nutzerprompts an den Assistant, versieht alle
    Calls mit Metadaten und erkennt Eskalationssignale."""

    def __init__(self) -> None:
        api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.client = AsyncOpenAI(api_key=api_key)
        # Merkt sich pro Session den zugehörigen Thread der Assistant API.
        self._threads: Dict[str, str] = {}
        self.assistant_id = ASSISTANT_ID

    async def ask_assistant(self, session_id: str, prompt: str) -> Tuple[str, bool]:
        """Sendet den Prompt an den Assistant und prüft, ob eskaliert werden muss.

        Rückgabe:
            (assistant_reply, escalation_needed)

        Ablauf:
        - Nutzt session_id als logische Thread-ID; Thread wird einmalig erstellt.
        - Sendet Metadaten (session_id, app) an Thread, Message und Run, damit
          die Anfrage im OpenAI-Dashboard nachvollziehbar ist.
        - Startet einen Run und pollt im Sekundentakt, bis der Status 'completed' ist.
        - Prüft die Antwort auf das Eskalations-Token (ESKALATION_NOETIG).
        """
        thread_id = self._threads.get(session_id)
        if thread_id is None:
            thread = await self.client.beta.threads.create(
                metadata={"session_id": session_id, "app": "SecureGateway"}
            )
            thread_id = thread.id
            self._threads[session_id] = thread_id

        # Nachricht in den Thread legen
        logging.info(f"OpenAI Request [Session {session_id}]: {prompt}")
        await self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt,
            metadata={"session_id": session_id, "app": "SecureGateway"},
        )

        # Run starten
        run = await self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
            metadata={"session_id": session_id, "app": "SecureGateway"},
        )

        # Polling bis abgeschlossen
        while run.status != "completed":
            await asyncio.sleep(0.5)  # Optimiertes Polling-Intervall
            run = await self.client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run.id
            )

        # Letzte Nachricht abrufen
        messages = await self.client.beta.threads.messages.list(
            thread_id=thread_id, limit=1
        )
        if not messages.data:
            return "", True

        latest_message = messages.data[0]
        if not latest_message.content:
            return "", True

        content = latest_message.content[0].text.value
        logging.info(f"OpenAI Response [Session {session_id}]: {content}")

        # Eskalationssignal prüfen
        if "ESKALATION_NOETIG" in content:
            logging.info(f"Escalation triggered by AI response: {content}")
            return "", True

        return content, False

    async def get_thread_history(self, session_id: str) -> List[str]:
        """Ruft den gesamten Chat-Verlauf aus dem OpenAI Thread ab."""
        thread_id = self._threads.get(session_id)
        if not thread_id:
            return []

        try:
            # Hole alle Nachrichten im Thread (default sort ist desc, also neuste zuerst)
            messages = await self.client.beta.threads.messages.list(
                thread_id=thread_id,
                order="asc",  # Wir wollen chronologische Reihenfolge
                limit=100
            )

            history = []
            for msg in messages.data:
                role = msg.role  # 'user' oder 'assistant'
                if msg.content:
                    text = msg.content[0].text.value
                    history.append(f"{role.capitalize()}: {text}")

            return history
        except Exception as e:
            logging.error(f"Failed to fetch thread history for session {session_id}: {e}")
            return []
