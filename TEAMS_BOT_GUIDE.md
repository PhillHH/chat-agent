# Microsoft Teams Bot Integration Guide

Dieser Guide beschreibt, wie das Backend mit Microsoft Teams verbunden wird, um eine bidirektionale Kommunikation zwischen Web-Usern und Support-Mitarbeitern in Teams zu ermöglichen.

## 1. Voraussetzungen

*   Zugriff auf das **Azure Portal** (https://portal.azure.com).
*   Berechtigung, eine **Azure Bot** Ressource zu erstellen.
*   Eine HTTPS-URL für das Backend (z.B. via Tunnel wie ngrok für lokale Entwicklung). Microsoft Teams kann nicht mit `localhost` kommunizieren.

## 2. Azure Bot Ressource erstellen

1.  Suche im Azure Portal nach **"Azure Bot"**.
2.  Erstelle eine neue Ressource.
    *   **Bot Handle:** Eindeutiger Name (z.B. `PolarisDX-Bot`).
    *   **Subscription/Resource Group:** Wähle deine Umgebung.
    *   **Pricing Tier:** Free (F0) reicht für Tests.
    *   **Type of App:** "Multi Tenant" (Standard).
3.  Nach der Erstellung, gehe zur Ressource -> **Configuration**.
    *   Kopiere die **Microsoft App ID**.
    *   Klicke auf "Manage Password" (führt zu Key Vault/Entra ID), erstelle ein neues Client Secret und kopiere das **Value** (nicht die ID!).

## 3. Konfiguration im Backend

Setze die folgenden Umgebungsvariablen in deiner `.env` Datei oder der Deployment-Umgebung:

```bash
MICROSOFT_APP_ID="<Deine-App-ID>"
MICROSOFT_APP_PASSWORD="<Dein-App-Password>"
```

Starten Sie das Backend neu.

## 4. Messaging Endpoint konfigurieren

1.  Gehe zurück zur Azure Bot Ressource -> **Configuration**.
2.  Setze den **Messaging Endpoint** auf die öffentliche URL deines Backends + `/api/messages`.
    *   Beispiel: `https://mein-backend.azurewebsites.net/api/messages`
    *   Bei lokaler Entwicklung mit ngrok: `https://<ngrok-id>.ngrok.io/api/messages`

## 5. Kanal "Microsoft Teams" aktivieren

1.  Gehe zur Azure Bot Ressource -> **Channels**.
2.  Wähle das Icon für **Microsoft Teams**.
3.  Akzeptiere die Nutzungsbedingungen und klicke auf **Save**.

## 6. Testen

1.  Starte das Backend.
2.  Öffne das Test-Frontend (`/test-chat` oder `/static/chat_v2.html`).
3.  Starte einen Chat.
    *   Die Nachricht sollte *nicht* sofort in Teams erscheinen, es sei denn, der Bot wurde *proaktiv* in einen Kanal eingeladen und wir haben die `ConversationReference`.
    *   *Aktuell implementiert:* Der Bot antwortet im Web-Chat.
4.  Um die **Eskalation** zu testen:
    *   Schreibe "Ich will einen Menschen sprechen" (oder trigger das Keyword `ESKALATION_NOETIG`).
    *   Das Backend sendet eine Adaptive Card an den konfigurierten Webhook (alter Weg) oder nutzt den Bot-Kontext (wenn verfügbar).

**Hinweis zur direkten Kommunikation:**
Damit der Bot Nachrichten in einen Teams-Kanal posten kann, muss er dort **erwähnt** werden (`@PolarisDX-Bot`), oder der User muss dem Bot eine DM schreiben. Sobald der Bot eine Nachricht empfängt, speichert das Backend die `ConversationReference` und kann zukünftige Nachrichten dorthin routen.

*Empfohlener Flow:*
1.  User startet Chat im Web.
2.  Bei Eskalation sendet das System eine Nachricht an einen Teams-Kanal (via Webhook), die einen Link zum Bot-Chat (Deep Link) enthält oder den Bot @mentions.
