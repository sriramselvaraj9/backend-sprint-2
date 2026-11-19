import redis.asyncio as redis

from app.core.config import settings

# ---------------------------------------------------------
# Shared Async Redis Client Connection Pool
# ---------------------------------------------------------
# Created once at module load using the centralized settings object
# max_connections=10 ensures connection pooling across requests
redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=10,
)


async def get_redis() -> redis.Redis:
    """
    FastAPI dependency that provides the shared Redis client instance.
    Reuses the single client instance across requests without creating new pools.
    """
    return redis_client
