"""Token bucket rate limits. Spec: docs/03-specs/01-api-bff.md §4."""

import asyncio
import time
from dataclasses import dataclass

from prometheus_client import Counter

from ar_common.metrics import REGISTRY

# The series stays registered so an old dashboard does not break. It is not incremented:
# a Valkey outage denies the request instead of allowing it.
BYPASS = Counter(
    "ar_ratelimit_bypass_total",
    "Requests allowed because Valkey rate limiting was unavailable.",
    registry=REGISTRY,
)
UNAVAILABLE = Counter(
    "ar_ratelimit_unavailable_total",
    "Requests denied because Valkey rate limiting was unavailable.",
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
    """Valkey-backed fixed window shared by every replica.

    A blip is retried. The limiter never latches open: when Valkey stays down the
    request is denied.
    """

    def __init__(
        self,
        url: str,
        *,
        client: object | None = None,
        attempts: int = 3,
        pause_s: float = 0.02,
    ) -> None:
        self.url = url
        self._redis = client
        self._injected = client is not None
        self.attempts = max(1, attempts)
        self.pause_s = pause_s

    async def take(self, key: str, limit: int, *, now: float | None = None) -> RateDecision:
        del now
        for attempt in range(self.attempts):
            try:
                client = self._client()
                count = int(await client.incr(key))  # type: ignore[attr-defined]
                if count == 1:
                    await client.expire(key, 60)  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001 - deny after the retries are spent
                if not self._injected:
                    self._redis = None
                if attempt + 1 < self.attempts:
                    await asyncio.sleep(self.pause_s * (attempt + 1))
                    continue
                UNAVAILABLE.inc()
                return RateDecision(allowed=False, limit=limit, remaining=0, reset_s=60)
            remaining = max(limit - count, 0)
            return RateDecision(
                allowed=count <= limit,
                limit=limit,
                remaining=remaining,
                reset_s=60,
            )
        return RateDecision(allowed=False, limit=limit, remaining=0, reset_s=60)  # pragma: no cover

    def _client(self) -> object:
        if self._redis is None:
            from ar_common.valkey import valkey_client  # noqa: PLC0415

            self._redis = valkey_client(self.url, socket_connect_timeout=1, socket_timeout=1)
        return self._redis
