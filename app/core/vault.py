"""Kapselt den PII-Vault des Secure AI Gateways und legt sensible Daten
temporär in Redis ab (TTL: 1h für PII, 24h für Statuswechsel)."""
from uuid import uuid4

from app.core.database import redis_client as default_redis_client

# Präfix für Status-Keys im Vault.
STATUS_PREFIX = "status:"


class PIIVault:
    """Verantwortlich für das Speichern und Wiederherstellen von PII.
    Nutzt Redis als kurzlebigen Speicher, um Platzhalter aufzulösen."""

    def __init__(self, redis_conn=None, ttl_seconds: int = 3600):
        self.redis = redis_conn or default_redis_client
        self.ttl_seconds = ttl_seconds

    def store(self, text: str, entity_type: str) -> str:
        """Speichert den Originalwert unter einem Platzhalter in Redis.

        Redis setzt per TTL sicher, dass PII nach Ablauf der Sitzung
        automatisch gelöscht wird (Privacy by Design).
        """
        # Kürzerer UUID-Suffix erzeugt kompakte Platzhalter.
        placeholder = f"<{entity_type.upper()}_{uuid4().hex[:8]}>"
        self.redis.setex(placeholder, self.ttl_seconds, text)
        return placeholder

    def get(self, placeholder: str) -> str:
        value = self.redis.get(placeholder)
        return value if value is not None else placeholder

    def set_status(self, session_id: str, mode: str) -> None:
        """Setzt den Chat-Modus (AI/HUMAN) mit verlängerter TTL in Redis."""
        key = f"{STATUS_PREFIX}{session_id}"
        # 24h TTL, damit menschliche Bearbeitung ausreichend Zeit hat.
        self.redis.setex(key, 24 * 3600, mode)

    def get_status(self, session_id: str) -> str:
        """Liest den Chat-Modus aus Redis; Standard ist AI."""
        key = f"{STATUS_PREFIX}{session_id}"
        status = self.redis.get(key)
        return status if status is not None else "AI"


vault = PIIVault()

