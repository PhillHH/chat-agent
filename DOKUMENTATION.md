# Dokumentation: Secure PolarisDX AI-Chat Gateway & TrainingsHub

Diese Dokumentation beschreibt das Secure Chat Gateway, einschließlich des neu integrierten Verwaltungsbackends ("TrainingsHub"), der Schnittstellen und der Teams-Integration.

## 1. TrainingsHub (Verwaltungsbackend)

Der TrainingsHub ist ein leichtgewichtiges Backend zur Analyse, Bewertung und Verfeinerung von Chat-Verläufen. Er ermöglicht Administratoren und Trainern, die Interaktionen zwischen Nutzern und dem KI-Bot einzusehen.

### Aktivierung
Das Backend ist standardmäßig deaktiviert ("Small" & "Secure"). Um es zu aktivieren, muss die Environment-Variable `ENABLE_ADMIN_BACKEND` gesetzt werden:

```bash
export ENABLE_ADMIN_BACKEND=true
```

Ist diese Variable nicht gesetzt oder `false`, sind alle Admin-Endpunkte und das Frontend deaktiviert (HTTP 403).

### Funktionen
Das Dashboard ist unter `/admin-panel` erreichbar (sofern aktiviert). Es bietet folgende Funktionen:

1.  **Chat-Übersicht:** Eine Liste aller gespeicherten Chat-Sitzungen mit Datum und ID.
2.  **Detailansicht:** Beim Klick auf eine Session wird der komplette Verlauf (User & Bot Nachrichten) angezeigt.
3.  **Analyse & Notizen:** Zu jeder Session können Notizen (z.B. für Qualitätssicherung oder Training) erfasst und gespeichert werden.
4.  **Daten-Export:** Über den Button "CSV Exportieren" können alle Chats und Nachrichten inkl. Metadaten und Notizen als CSV-Datei heruntergeladen werden. Dies dient als Basis für offline Analysen oder das Fine-Tuning neuer Modelle.

---

## 2. Technische Schnittstelle: Frontend ↔ Chatbot

Das Chat-Frontend kommuniziert über eine REST-API oder WebSockets mit dem Gateway.

**Detaillierte Integrationsanleitung:** [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)

### Haupt-Endpunkt (WebSocket): `/chat/ws/{session_id}`
Dies ist der empfohlene Weg für moderne Chat-Interfaces. Er ermöglicht bidirektionale Kommunikation (Server kann Nachrichten vom Agenten pushen).

### Legacy Endpunkt (HTTP POST): `/chat/message`
Dient zum Senden von Nachrichten und Empfangen der Antwort per Server-Sent-Events (Streaming).

---

## 3. Anbindung an Microsoft Teams (Eskalation & Live-Chat)

Das System verfügt über eine bidirektionale Integration mit Microsoft Teams.

**Konfigurationsanleitung:** [TEAMS_BOT_GUIDE.md](TEAMS_BOT_GUIDE.md)

### Eskalation
Die Eskalation wird ausgelöst durch:
- Das Token `ESKALATION_NOETIG` in der Antwort der KI (vom System-Prompt gesteuert).

### Ablauf
1.  **Erkennung:** Der `ChatRouter` analysiert den Antwort-Stream der KI.
2.  **Status-Wechsel:** Der Status der Session wird auf `HUMAN` gesetzt.
3.  **Benachrichtigung:**
    - Eine Nachricht/Karte wird an Teams gesendet.
    - Ab jetzt werden Nachrichten des Kunden direkt an Teams weitergeleitet.
    - Antworten des Mitarbeiters in Teams werden über den WebSocket direkt an den Kunden im Web-Chat gesendet.

---

## 4. Datenbank (Neu)

Für den TrainingsHub wurde eine lokale SQLite-Datenbank (`training_hub.db`) eingeführt.
- **Technologie:** SQLite (via SQLAlchemy)
- **Schema:**
    - `chat_sessions`: ID, Erstellzeit, Notizen
    - `chat_messages`: ID, Session-ID, Rolle (User/Assistant), Inhalt, Zeitstempel
- **Datenschutz:** Diese DB speichert die Konversationen lokal auf dem Server. Beachten Sie die DSGVO-Richtlinien beim Export und der Langzeitspeicherung.
