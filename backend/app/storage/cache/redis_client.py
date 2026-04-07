"""
Redis client setup.

Initialised once at application startup via the FastAPI lifespan.
The client is stored on `app.state.redis` for use by later packages.

If REDIS_URL is not configured or Redis is unreachable the module is a
no-op so that the existing functionality is completely unaffected.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


async def build_redis_client(redis_url: str) -> aioredis.Redis | None:
    """
    Create an async Redis client and verify connectivity with PING.
    Returns None when redis_url is empty or the server is unreachable.
    """
    if not redis_url:
        logger.info("REDIS_URL not set — Redis client disabled")
        return None

    try:
        client = aioredis.from_url(redis_url, decode_responses=True)
        await client.ping()
        logger.info("Redis client ready")
        return client
    except Exception as exc:
        logger.warning("Redis client init failed: %s", exc)
        return None


@asynccontextmanager
async def redis_lifespan(
    redis_url: str,
) -> AsyncGenerator[aioredis.Redis | None, None]:
    """
    Async context manager for use inside FastAPI lifespan.
    Yields the Redis client (or None if Redis is unavailable).
    """
    client = await build_redis_client(redis_url)
    try:
        yield client
    finally:
        if client is not None:
            await client.aclose()
            logger.info("Redis client closed")
