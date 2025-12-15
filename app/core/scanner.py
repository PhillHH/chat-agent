import re
from typing import List, Dict, Any

from gliner import GLiNER

from app.core.vault import PIIVault, vault


class PIIScanner:
    def __init__(self, vault_instance: PIIVault = vault):
        self.vault = vault_instance
        # Modell wird einmalig beim Start geladen
        self.model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
        # Regex-Pattern vorbereiten
        self.email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        self.phone_pattern = re.compile(
            r"(\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,5}\)?[\s\-]?)?\d[\d\s\-]{5,}\d"
        )

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

    def clean(self, text: str) -> str:
        # Schritt A: Regex-basierte PII vorab entfernen
        text = self._clean_regex(text)

        # Schritt B: GLiNER-Entities erkennen
        entities: List[Dict[str, Any]] = self.model.predict_entities(
            text, labels=["person", "organization", "city"]
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

        return text

