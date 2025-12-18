"""PII-Scanner des Secure PolarisDX AI-Chat Gateways: anonymisiert Eingaben
(Regex + GLiNER) und stellt Originalwerte nach der KI-Antwort wieder her
(Re-Personalisierung)."""
import re
import logging
import asyncio
from typing import List, Dict, Any

from gliner import GLiNER

from app.core.vault import PIIVault, vault

logger = logging.getLogger(__name__)


class PIIScanner:
    """Filtert PII, speichert Originalwerte im Vault und stellt sie nach
    der Modellverarbeitung wieder her."""

    def __init__(self, vault_instance: PIIVault = vault):
        self.vault = vault_instance
        # Modell wird einmalig beim Start geladen (vermeidet Latenz pro Anfrage).
        self.model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
        # Regex-Pattern für schnelle Vorfilterung typischer PII (ergänzt GLiNER).
        self.email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        self.phone_pattern = re.compile(
            r"(\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,5}\)?[\s\-]?)?\d[\d\s\-]{5,}\d"
        )
        self.placeholder_pattern = re.compile(r"<[A-Z]+_[^>]+>")

    def _clean_regex(self, text: str) -> str:
        # E-Mails ersetzen
        def replace_email(match: re.Match) -> str:
            original = match.group(0)
            return self.vault.store(original, "EMAIL")

        text = self.email_pattern.sub(replace_email, text)

        # Telefonnummern ersetzen
        def replace_phone(match: re.Match) -> str:
            original = match.group(0)
            return self.vault.store(original, "PHONE")

        text = self.phone_pattern.sub(replace_phone, text)
        return text

    async def clean(self, text: str) -> str:
        """Anonymisiert PII, indem erkannte Werte durch Vault-Platzhalter
        ersetzt werden; erfüllt den DSGVO-Schritt vor der Modellnutzung.

        Schritte:
        - Regex-Phase (Emails, Telefonnummern) zur schnellen Vorfilterung.
        - GLiNER-Phase (Person/Organisation/Stadt) mit Score-Filter.
        - Platzhalter werden im Vault abgelegt und ersetzen den Textinhalt.
        """
        original_text = text
        # Schritt A: Regex-basierte PII vorab entfernen
        text = self._clean_regex(text)

        # Schritt B: GLiNER-Entities erkennen
        # CPU-intensive Tasks in ThreadPool auslagern, um Blocking zu verhindern
        loop = asyncio.get_running_loop()
        entities: List[Dict[str, Any]] = await loop.run_in_executor(
            None,
            lambda: self.model.predict_entities(
                text, labels=["person", "organization", "city"]
            )
        )

        # Schritt C: Platzhalter einsetzen (von hinten nach vorne, um Indizes stabil zu halten)
        for entity in sorted(entities, key=lambda e: e.get("start", 0), reverse=True):
            score = entity.get("score", 0)
            if score < 0.7:
                continue

            start = entity.get("start")
            end = entity.get("end")
            label = entity.get("label", "entity")
            if start is None or end is None or start < 0 or end > len(text):
                continue

            original = text[start:end]
            placeholder = self.vault.store(original, label)
            text = text[:start] + placeholder + text[end:]

        logger.info(f"PII Clean: Original='{original_text}' -> Anonymized='{text}'")
        return text

    def restore(self, text: str) -> str:
        """Re-personalisiert die KI-Antwort, indem Platzhalter über den
        Vault aufgelöst und durch Originalwerte ersetzt werden.

        - Findet alle Platzhalter im Text via Regex.
        - Holt Originalwerte aus dem Vault (Redis).
        - Ersetzt Platzhalter für die finale Antwort an den Nutzer.
        """
        # Platzhalter im Text durch Originalwerte aus dem Vault ersetzen
        def replace_placeholder(match: re.Match) -> str:
            placeholder = match.group(0)
            return self.vault.get(placeholder)

        return self.placeholder_pattern.sub(replace_placeholder, text)

    async def restore_stream(self, token_generator):
        """Streaming-Version von restore. Nimmt einen Generator von Tokens entgegen
        und yieldet die Tokens, wobei Platzhalter on-the-fly ersetzt werden."""
        buffer = ""
        async for token in token_generator:
            buffer += token

            while True:
                # Suche nach Beginn eines Platzhalters
                start_idx = buffer.find("<")
                if start_idx == -1:
                    # Kein '<' gefunden, Puffer sicher ausgeben
                    if buffer:
                        yield buffer
                        buffer = ""
                    break

                # Wir haben ein '<'. Alles davor ausgeben.
                if start_idx > 0:
                    yield buffer[:start_idx]
                    buffer = buffer[start_idx:]
                    # buffer beginnt jetzt mit '<'

                # Suche nach Ende des Platzhalters
                end_idx = buffer.find(">")
                if end_idx != -1:
                    # Kompletter Tag gefunden
                    candidate = buffer[: end_idx + 1]

                    # Validieren, ob es ein bekannter PII-Platzhalter ist
                    if self.placeholder_pattern.fullmatch(candidate):
                        # Ersetzen
                        original = self.vault.get(candidate)
                        yield original
                    else:
                        # Kein PII-Platzhalter (z.B. <br> oder < 5), original ausgeben
                        yield candidate

                    buffer = buffer[end_idx + 1 :]
                else:
                    # '<' ist da, aber kein '>'.
                    # Check, ob es überhaupt ein gültiger Anfang sein kann.
                    # Unsere Platzhalter fangen mit <[A-Z] an.
                    # Wenn das Zeichen nach < kein Großbuchstabe ist, ist es kein PII-Tag.
                    # (Ausnahme: Puffer ist nur "<")
                    if len(buffer) > 1:
                        second_char = buffer[1]
                        # Wenn kein Großbuchstabe, dann ist es kein PII-Start
                        if not ("A" <= second_char <= "Z"):
                            yield buffer[0]
                            buffer = buffer[1:]
                            continue

                    # Es könnte ein valider Anfang sein, wir warten auf mehr Tokens.
                    break

        # Reste im Puffer ausgeben
        if buffer:
            yield buffer
