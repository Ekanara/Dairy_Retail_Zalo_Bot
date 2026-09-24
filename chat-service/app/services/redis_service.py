"""
Redis cache service for chat-service.

Uses Redis ZSET (sorted set) for efficient top-K message caching.

Key pattern:
    chat:user:{user_id}      — messages for a user_id
    chat:window:{window_id}  — messages for a window_id

Each entry:
    Score: Unix timestamp (created_at)
    Value: JSON-serialized message dict

Public API
----------
cache_message(key_suffix, message)              → None
get_messages(key_suffix, limit)                 → list[dict] | None
invalidate(key_suffix)                          → None
close()                                         → None (shutdown cleanup)
"""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class RedisCache:
    """Async Redis client for chat message caching."""

    def __init__(self) -> None:
        self.redis: aioredis.Redis | None = None
        self.ttl = settings.CACHE_TTL

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        if self.redis is None:
            self.redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )
            logger.info("redis.connected", url=settings.REDIS_URL)

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self.redis is not None:
            await self.redis.close()
            self.redis = None
            logger.info("redis.closed")

    async def cache_message(
        self,
        key_suffix: str,
        message: dict[str, Any],
        timestamp: float,
    ) -> None:
        """
        Add a message to the Redis ZSET cache.

        Parameters
        ----------
        key_suffix : 'user:{user_id}' or 'window:{window_id}'
        message    : Message dict to cache (will be JSON-serialized)
        timestamp  : Unix timestamp (used as ZSET score)
        """
        if self.redis is None:
            await self.connect()

        key = f"chat:{key_suffix}"
        value = json.dumps(message, default=str)

        t0 = time.monotonic()
        async with self.redis.pipeline(transaction=True) as pipe:
            # Add to sorted set (score = timestamp)
            await pipe.zadd(key, {value: timestamp})
            # Set TTL
            await pipe.expire(key, self.ttl)
            await pipe.execute()

        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "redis.cache_message",
            key=key,
            latency_ms=latency_ms,
        )

    async def get_messages(
        self,
        key_suffix: str,
        limit: int = 100,
    ) -> list[dict[str, Any]] | None:
        """
        Retrieve top-K messages from Redis ZSET.

        Parameters
        ----------
        key_suffix : 'user:{user_id}' or 'window:{window_id}'
        limit      : Max number of messages to return

        Returns
        -------
        List of message dicts (newest first), or None if cache miss.
        """
        if self.redis is None:
            await self.connect()

        key = f"chat:{key_suffix}"
        t0 = time.monotonic()

        # ZREVRANGE: get top-K by score DESC (newest first)
        raw_messages = await self.redis.zrevrange(key, 0, limit - 1)

        if not raw_messages:
            logger.info("redis.cache_miss", key=key)
            return None

        messages = [json.loads(msg) for msg in raw_messages]
        latency_ms = round((time.monotonic() - t0) * 1000, 2)

        logger.info(
            "redis.cache_hit",
            key=key,
            count=len(messages),
            latency_ms=latency_ms,
        )
        return messages

    async def invalidate(self, key_suffix: str) -> None:
        """
        Delete a cache key.

        Parameters
        ----------
        key_suffix : 'user:{user_id}' or 'window:{window_id}'
        """
        if self.redis is None:
            await self.connect()

        key = f"chat:{key_suffix}"
        await self.redis.delete(key)
        logger.info("redis.invalidate", key=key)


# Global singleton instance
redis_cache = RedisCache()
