"""Valkey client factory. The server speaks the Redis protocol."""

from redis.asyncio import Redis


def valkey_client(url: str) -> Redis:
    """Return an asyncio Redis client for a Valkey (or Redis) URL."""
    return Redis.from_url(url, decode_responses=True)
