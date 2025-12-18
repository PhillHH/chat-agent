"""Steuert die Kommunikation mit der OpenAI Assistant API inkl.
Eskalationslogik für das Secure PolarisDX AI-Chat Gateway."""
import os
import asyncio
import logging
from typing import Dict, Tuple, List

from openai import AsyncOpenAI
from openai import AsyncAssistantEventHandler
from typing_extensions import override
import asyncio

from app.core.config import settings

# Platzhalter-Assistent; kann über Settings/Env überschrieben werden.
ASSISTANT_ID = settings.assistant_id

class EventHandler(AsyncAssistantEventHandler):
    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self.full_response = []

    @override
    async def on_text_delta(self, delta, snapshot):
        if delta.value:
            self.full_response.append(delta.value)
            await self.queue.put(delta.value)

    @override
    async def on_end(self):
        await self.queue.put(None)  # Signal end

class AIAssistant:
    """Sendet bereinigte Nutzerprompts an den Assistant, versieht alle
    Calls mit Metadaten und erkennt Eskalationssignale."""

    def __init__(self) -> None:
        api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self.client = AsyncOpenAI(api_key=api_key)
        # Merkt sich pro Session den zugehörigen Thread der Assistant API.
        self._threads: Dict[str, str] = {}
        self.assistant_id = ASSISTANT_ID

    async def _get_or_create_thread(self, session_id: str) -> str:
        thread_id = self._threads.get(session_id)
        if thread_id is None:
            thread = await self.client.beta.threads.create(
                metadata={"session_id": session_id, "app": "SecureGateway"}
            )
            thread_id = thread.id
            self._threads[session_id] = thread_id
        return thread_id

    async def ask_assistant_stream(self, session_id: str, prompt: str):
        """Streaming-Version von ask_assistant. Yieldet Text-Deltas.
        Rückgabe via Generator: tokens.
        Gibt am Ende (nach dem Generator) zurück, ob Eskalation nötig ist?
        Nein, Generator kann nur Werte yielden.

        Lösung: Wir yielden den Text. Die Prüfung auf Eskalation erfolgt parallel
        oder am Ende. Da wir hier einen Generator zurückgeben, kann der Aufrufer
        nicht einfach einen Return-Wert abfangen.
        Wir müssen dem Aufrufer eine Möglichkeit geben, das Full-Response-Resultat zu prüfen.
        """
        thread_id = await self._get_or_create_thread(session_id)

        # Nachricht in den Thread legen
        logging.info(f"OpenAI Request [Session {session_id}]: {prompt}")
        await self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=prompt,
            metadata={"session_id": session_id, "app": "SecureGateway"},
        )

        handler = EventHandler()

        # Start stream in background task to allow yielding from queue
        async def stream_task():
            try:
                async with self.client.beta.threads.runs.stream(
                    thread_id=thread_id,
                    assistant_id=self.assistant_id,
                    event_handler=handler,
                    metadata={"session_id": session_id, "app": "SecureGateway"},
                ) as stream:
                    await stream.until_done()
            except Exception as e:
                logging.error(f"Stream failed for session {session_id}: {e}")
            finally:
                # Signal end of stream even on error to unblock consumer
                await handler.queue.put(None)

        # Wir starten den Stream-Task nicht als Fire-and-Forget, sondern
        # wir müssen warten, aber gleichzeitig Queue konsumieren.
        # create_task schedule it.
        task = asyncio.create_task(stream_task())

        full_text = ""

        while True:
            token = await handler.queue.get()
            if token is None:
                break
            full_text += token
            yield token

        await task

        # Nach Ende des Streams prüfen wir auf Eskalation
        if "ESKALATION_NOETIG" in full_text:
             logging.info(f"Escalation triggered by AI response: {full_text}")
             # Hier können wir eine Exception werfen oder einen speziellen Token yielden?
             # Oder wir nutzen einen Callback / Shared State.
             # Da der Router Zugriff auf `app.state.notifier` hat, wäre es gut, wenn
             # wir das hier signalisieren.
             # Wir werfen eine spezielle Exception, die der Router fangen kann?
             # Aber der Router iteriert gerade über den Response-Body.
             # In FastAPI StreamingResponse exceptions zu raisen bricht den Stream ab (Client error).
             # Das ist okay. Wir wollen ja vielleicht die Benachrichtigung triggern.
             # Aber idealerweise machen wir das "out of band".

             # Besser: Wir geben das Signal an den Aufrufer zurück? Geht bei Generator schwer.
             # Wir speichern es im Thread-Objekt oder nutzen einen Callback?
             pass

        # Wir können das full_text Ergebnis im Handler speichern, falls nötig.
        # Aber der Router verarbeitet den Stream.

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
