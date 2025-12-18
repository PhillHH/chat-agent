# Frontend Integration Guide

Dieser Guide beschreibt, wie das Frontend (React/TypeScript) an das Secure PolarisDX AI-Chat Gateway angebunden wird.

## 1. WebSocket Verbindung

Für eine echtzeitfähige, bidirektionale Kommunikation (User <-> KI <-> Menschlicher Agent) wird WebSockets verwendet.

**Endpunkt:** `ws://<backend-url>/chat/ws/{session_id}`

### Verbindung aufbauen

Generiere eine eindeutige `session_id` auf dem Client (oder rufe sie vom Backend ab, falls authentifiziert).

```typescript
const sessionId = "sess_" + Math.random().toString(36).substr(2, 9);
const wsUrl = `ws://localhost:1985/chat/ws/${sessionId}`;
const socket = new WebSocket(wsUrl);

socket.onopen = () => {
    console.log("Verbunden mit Chat Gateway");
};
```

### Nachrichten senden (User -> Backend)

Nachrichten werden als JSON gesendet.

```typescript
const payload = {
    message: "Hallo, ich habe eine Frage zu meiner Rechnung."
};
socket.send(JSON.stringify(payload));
```

### Nachrichten empfangen (Backend -> User)

Das Backend sendet verschiedene Nachrichtentypen. Das Frontend sollte das Feld `type` auswerten.

```typescript
socket.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch (data.type) {
        case "chunk":
            // Teil einer KI-Antwort (Streaming)
            // Hänge data.text an die aktuelle Bot-Nachricht an
            updateBotMessage(data.text);
            break;

        case "done":
            // KI-Antwort ist fertig
            finalizeBotMessage();
            break;

        case "agent_message":
            // Nachricht von einem echten Menschen (aus Teams)
            // Zeige diese als separate Nachricht oder markiert an
            showAgentMessage(data.text, data.sender);
            break;

        case "system":
            // Systemnachricht (z.B. "Eskalation ausgelöst")
            showSystemNotification(data.text);
            break;

        case "error":
            console.error("Fehler:", data.text);
            break;
    }
};
```

## 2. Fallback: HTTP POST (Legacy/Alternative)

Falls WebSockets nicht möglich sind, kann der HTTP POST Endpunkt genutzt werden. Dieser unterstützt jedoch *keinen* Empfang von Nachrichten, die vom Agenten in Teams initiiert wurden (nur Polling oder unidirektional).

**Endpunkt:** `POST /chat/message`

**Body:**
```json
{
  "session_id": "sess_12345",
  "message": "Meine Frage"
}
```

**Response:** Text/Stream (Server-Sent Events Format) oder JSON (bei Fehlern/Statusmeldungen).

## 3. Typ-Definitionen (TypeScript)

```typescript
interface ChatMessage {
    type: 'chunk' | 'done' | 'agent_message' | 'system' | 'error';
    text?: string;
    sender?: string; // z.B. "Agent"
    status?: string; // z.B. "HUMAN_MODE"
}
```
