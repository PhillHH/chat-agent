import redis

from app.core.config import settings


def get_redis_client() -> redis.Redis:
    client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )
    client.ping()
    return client


redis_client = get_redis_client()

