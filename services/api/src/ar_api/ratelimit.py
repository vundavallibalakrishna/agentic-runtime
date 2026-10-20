"""Token bucket rate limits. Spec: docs/03-specs/01-api-bff.md §4."""

import time
from dataclasses import dataclass

from prometheus_client import Counter

from ar_common.metrics import REGISTRY

BYPASS = Counter(
    "ar_ratelimit_bypass_total",
    "Requests allowed because Valkey rate limiting was unavailable.",
    registry=REGISTRY,
)


@dataclass(frozen=True, slots=True)
class RateDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_s: int


class MemoryTokenBucket:
    """Process-local bucket used in tests and when Valkey is not required."""

    def __init__(self) -> None:
        self._hits: dict[str, tuple[float, int]] = {}

    async def take(self, key: str, limit: int, *, now: float | None = None) -> RateDecision:
        clock = time.monotonic() if now is None else now
        window = int(clock // 60)
        slot, count = self._hits.get(key, (window, 0))
        if slot != window:
            count = 0
        count += 1
        self._hits[key] = (window, count)
        remaining = max(limit - count, 0)
        return RateDecision(
            allowed=count <= limit,
            limit=limit,
            remaining=remaining,
            reset_s=60 - int(clock % 60),
        )


class ValkeyTokenBucket:
    """Valkey-backed fixed window. Fails open after the first connection error."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._redis: object | None = None
        self._open = False

    async def take(self, key: str, limit: int, *, now: float | None = None) -> RateDecision:
        del now
        if self._open:
            BYPASS.inc()
            return RateDecision(allowed=True, limit=limit, remaining=limit, reset_s=60)
        try:
            client = self._client()
            count = int(await client.incr(key))  # type: ignore[attr-defined]
            if count == 1:
                await client.expire(key, 60)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - Valkey outages fail open
            self._open = True
            BYPASS.inc()
            return RateDecision(allowed=True, limit=limit, remaining=limit, reset_s=60)
        remaining = max(limit - count, 0)
        return RateDecision(allowed=count <= limit, limit=limit, remaining=remaining, reset_s=60)

    def _client(self) -> object:
        if self._redis is None:
            from ar_common.valkey import valkey_client  # noqa: PLC0415

            self._redis = valkey_client(self.url)
        return self._redis
