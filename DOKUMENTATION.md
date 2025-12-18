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

Das Chat-Frontend kommuniziert über eine REST-API mit dem Gateway.

### Endpunkt: `/chat/message` (POST)
Dient zum Senden von Nachrichten und Empfangen der Antwort.

**Request Body (JSON):**
```json
{
  "session_id": "string",  // Eindeutige ID der Sitzung
  "message": "string"      // Nachricht des Nutzers
}
```

**Antwort-Verhalten:**
Die API entscheidet dynamisch über das Antwortformat:

1.  **Streaming Response (Standard):**
    - Überträgt die KI-Antwort Token für Token (Text/Plain Stream).
    - Dies ermöglicht eine geringe Latenz ("Time to First Byte").
    - PII (personenbezogene Daten) werden "on-the-fly" wiederhergestellt.
    - Das Frontend muss diesen Stream lesen und inkrementell anzeigen.

2.  **JSON Response (Spezialfälle):**
    - Tritt auf bei `HUMAN_MODE` (Mensch übernimmt) oder Fehlern.
    - Format:
      ```json
      {
        "session_id": "...",
        "response": "Ein menschlicher Mitarbeiter...",
        "status": "HUMAN_MODE"
      }
      ```

**Ablauf im Backend:**
1.  **PII-Filterung:** Die Nachricht wird gescannt (Regex + GLiNER) und anonymisiert.
2.  **Persistenz:** Die Original-Nachricht (User) wird in der SQLite-Datenbank gespeichert.
3.  **AI-Inferenz:** Der anonymisierte Text geht an Azure OpenAI / OpenAI.
4.  **Re-Personalisierung:** Die Antwort der KI wird gestreamt, wobei Platzhalter (z.B. `<PERSON_1>`) durch die echten Daten aus dem Vault ersetzt werden.
5.  **Persistenz:** Der fertig zusammengesetzte Antworttext wird asynchron in der Datenbank gespeichert.

---

## 3. Anbindung an Microsoft Teams (Eskalation)

Das System verfügt über eine automatische Eskalationslogik, wenn die KI nicht weiterweiß oder der Nutzer einen menschlichen Mitarbeiter anfordert.

### Trigger
Die Eskalation wird ausgelöst durch:
- Das Token `ESKALATION_NOETIG` in der Antwort der KI (vom System-Prompt gesteuert).
- (Optional) Explizite Logik im Code.

### Ablauf
1.  **Erkennung:** Der `ChatRouter` analysiert den Antwort-Stream der KI. Wird das Eskalations-Token gefunden, bricht er den normalen KI-Modus ab.
2.  **Status-Wechsel:** Der Status der Session im `PIIVault` wird auf `HUMAN` gesetzt. Ab jetzt werden alle weiteren Nachrichten an `/chat/message` mit einer Standardantwort ("Bitte warten...") beantwortet, bis ein Mensch übernimmt (bzw. der Status zurückgesetzt wird).
3.  **Benachrichtigung:**
    - Der `TeamsNotifier` sammelt den gesamten Chat-Verlauf (aus dem OpenAI Thread History).
    - Er sendet eine **Adaptive Card** an einen konfigurierten Teams Webhook (`TEAMS_WEBHOOK_URL`).
    - Die Karte enthält:
        - Session ID
        - Den kompletten bisherigen Dialog
        - Hinweis auf Dringlichkeit

### Konfiguration
Die URL für den Webhook wird in den Environment-Variables hinterlegt:
```bash
TEAMS_WEBHOOK_URL="https://outlook.office.com/webhook/..."
```

---

## 4. Datenbank (Neu)

Für den TrainingsHub wurde eine lokale SQLite-Datenbank (`training_hub.db`) eingeführt.
- **Technologie:** SQLite (via SQLAlchemy)
- **Schema:**
    - `chat_sessions`: ID, Erstellzeit, Notizen
    - `chat_messages`: ID, Session-ID, Rolle (User/Assistant), Inhalt, Zeitstempel
- **Datenschutz:** Diese DB speichert die Konversationen lokal auf dem Server. Beachten Sie die DSGVO-Richtlinien beim Export und der Langzeitspeicherung.
