from uuid import uuid4

from app.core.database import redis_client as default_redis_client


class PIIVault:
    def __init__(self, redis_conn=None, ttl_seconds: int = 3600):
        self.redis = redis_conn or default_redis_client
        self.ttl_seconds = ttl_seconds

    def store(self, text: str, entity_type: str) -> str:
        placeholder = f"<{entity_type.upper()}_{uuid4().hex[:8]}>"
        self.redis.setex(placeholder, self.ttl_seconds, text)
        return placeholder

    def get(self, placeholder: str) -> str:
        value = self.redis.get(placeholder)
        return value if value is not None else placeholder


vault = PIIVault()

