# Projekt: Secure Customer AI Gateway

## 1. Management Summary

Entwicklung eines intelligenten Chatbots als DSGVO-konforme Middleware.

**Kernfunktion:**

1. Filtert personenbezogene Daten (PII) lokal (Server-Side) heraus.

2. Sendet anonymisierte Anfragen an OpenAI.

3. Re-Personalisiert die Antwort vor der Ausspielung.

4. Eskaliert an MS Teams bei Unwissenheit oder Problemen.

## 2. Tech Stack

- **Backend:** Python (FastAPI)
- **PII Filter:** GLiNER (Named Entity Recognition)
- **State Store:** Redis (Mapping von ID <-> Echtname)
- **AI Engine:** OpenAI Assistant API (mit File Search)
- **Integration:** MS Teams Webhooks
- **Container:** Docker & Docker Compose

## 3. 30-Punkte-Plan (Phasen)

### Phase 1: Setup & Infrastruktur

- [ ] 01. Projektordner anlegen (/app, /data)
- [ ] 02. Git Repository initialisieren (.gitignore für .env!)
- [ ] 03. requirements.txt erstellen
- [ ] 04. Dockerfile schreiben
- [ ] 05. docker-compose.yml anlegen
- [ ] 06. .env Datei erstellen

### Phase 2: Der "PII-Tresor" (Datenschutz)

- [ ] 07. Redis-Verbindung herstellen
- [ ] 08. Vault-Klasse schreiben (ID <-> Name)
- [ ] 09. Regex-Funktion bauen (Emails, Tel)
- [ ] 10. GLiNER Modell-Loader implementieren
- [ ] 11. GLiNER Filter-Funktion bauen
- [ ] 12. Pydantic-Modell UserMessage
- [ ] 13. Restore-Funktion bauen
- [ ] 14. Testlauf Filterung

### Phase 3: Die Intelligenz (OpenAI)

- [ ] 15. OpenAI Assistant anlegen
- [ ] 16. Firmenwissen hochladen
- [ ] 17. System Prompt definieren
- [ ] 18. Funktion ask_assistant implementieren
- [ ] 19. Eskalations-Trigger einbauen

### Phase 4: MS Teams & Steuerung

- [ ] 20. Webhook in Teams erstellen
- [ ] 21. JSON-Payload bauen
- [ ] 22. Funktion notify_teams implementieren
- [ ] 23. Status-Logik in Redis ('AI' vs 'HUMAN')
- [ ] 24. Weiche einbauen (Skip AI if Human)

### Phase 5: API & Integration

- [ ] 25. FastAPI Grundgerüst (main.py)
- [ ] 26. Endpoint POST /chat
- [ ] 27. Ablaufkette verknüpfen
- [ ] 28. Docker Container starten
- [ ] 29. Test 1: Wissensfrage (RAG)
- [ ] 30. Test 2: Datenschutz & Eskalation

