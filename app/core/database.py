"""Verbindet das Secure AI Gateway mit Redis und stellt einen synchronen
Client für PII-Storage und Retrieval bereit."""
import redis

from app.core.config import settings


def get_redis_client() -> redis.Redis:
    # Synchrone Redis-Verbindung; decode_responses=True liefert Strings statt Bytes.
    client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )
    client.ping()
    return client


redis_client = get_redis_client()

