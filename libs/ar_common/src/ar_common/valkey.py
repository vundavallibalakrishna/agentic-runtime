"""Valkey client factory. The server speaks the Redis protocol."""

from redis import Redis as SyncRedis
from redis.asyncio import Redis


def valkey_client(
    url: str,
    *,
    socket_connect_timeout: float | None = None,
    socket_timeout: float | None = None,
) -> Redis:
    """Return an asyncio Redis client for a Valkey (or Redis) URL."""
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=socket_connect_timeout,
        socket_timeout=socket_timeout,
    )


def valkey_sync_client(
    url: str,
    *,
    socket_connect_timeout: float | None = None,
    socket_timeout: float | None = None,
) -> SyncRedis:
    """Return a synchronous client. Rate windows and builder sessions use it."""
    return SyncRedis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=socket_connect_timeout,
        socket_timeout=socket_timeout,
    )
