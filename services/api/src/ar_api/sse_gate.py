"""Shared SSE cap. Counts live in Valkey so a second replica sees them."""

from ar_common.valkey import valkey_client


class ValkeySseGate:
    """``INCR`` / ``DECR`` on ``ar:sse:{user}``. The cap is not process-local."""

    def __init__(self, url: str, *, client: object | None = None) -> None:
        self.url = url
        self._client = client

    def _redis(self) -> object:
        if self._client is None:
            self._client = valkey_client(self.url)
        return self._client

    async def acquire(self, user_id: str, limit: int) -> bool:
        client = self._redis()
        key = f"ar:sse:{user_id}"
        count = int(await client.incr(key))  # type: ignore[attr-defined]
        if count == 1:
            await client.expire(key, 3600)  # type: ignore[attr-defined]
        if count > limit:
            await client.decr(key)  # type: ignore[attr-defined]
            return False
        return True

    async def release(self, user_id: str) -> None:
        client = self._redis()
        key = f"ar:sse:{user_id}"
        count = int(await client.decr(key))  # type: ignore[attr-defined]
        if count < 0:
            await client.set(key, "0", ex=3600)  # type: ignore[attr-defined]
