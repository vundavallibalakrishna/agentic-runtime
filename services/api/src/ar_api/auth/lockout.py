"""Shared login lockout.

The counter and the lock live in Valkey when more than one API replica serves
sign-in. A Valkey outage fails closed: the attempt is not allowed.
"""

from __future__ import annotations

import hashlib

from ar_common.errors import UnavailableError
from ar_common.time import utcnow


def lockout_subject(email: str) -> str:
    """Stable key for an address. The address itself is not the Valkey key."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


class MemoryLoginLockout:
    """Process-local lockout used in dev, CI, and unit tests."""

    def __init__(self, *, max_attempts: int = 10, lockout_s: int = 300) -> None:
        self.max_attempts = max(1, max_attempts)
        self.lockout_s = max(1, lockout_s)
        self._counts: dict[str, int] = {}
        self._until: dict[str, float] = {}

    async def retry_after(self, subject: str) -> int:
        until = self._until.get(subject, 0.0)
        remain = int(until - utcnow().timestamp())
        if remain > 0:
            return remain
        self._until.pop(subject, None)
        return 0

    async def record_failure(self, subject: str) -> int:
        locked = await self.retry_after(subject)
        if locked:
            return locked
        count = self._counts.get(subject, 0) + 1
        self._counts[subject] = count
        if count >= self.max_attempts:
            self._until[subject] = utcnow().timestamp() + self.lockout_s
            self._counts.pop(subject, None)
            return self.lockout_s
        return 0

    async def clear(self, subject: str) -> None:
        self._counts.pop(subject, None)
        self._until.pop(subject, None)


class ValkeyLoginLockout:
    """Lockout shared by every API replica. Keys are ``ar:lockout:*``."""

    def __init__(
        self,
        url: str,
        *,
        client: object | None = None,
        max_attempts: int = 10,
        lockout_s: int = 300,
    ) -> None:
        self.url = url
        self._redis = client
        self.max_attempts = max(1, max_attempts)
        self.lockout_s = max(1, lockout_s)

    async def retry_after(self, subject: str) -> int:
        try:
            ttl = int(await self._client().ttl(self._lock(subject)))  # type: ignore[attr-defined]
        except Exception as exc:
            raise _down() from exc
        return ttl if ttl > 0 else 0

    async def record_failure(self, subject: str) -> int:
        locked = await self.retry_after(subject)
        if locked:
            return locked
        try:
            client = self._client()
            count = int(await client.incr(self._count(subject)))  # type: ignore[attr-defined]
            if count >= self.max_attempts:
                await client.set(self._lock(subject), "1", ex=self.lockout_s)  # type: ignore[attr-defined]
                await client.delete(self._count(subject))  # type: ignore[attr-defined]
                return self.lockout_s
        except UnavailableError:
            raise
        except Exception as exc:
            raise _down() from exc
        return 0

    async def clear(self, subject: str) -> None:
        try:
            await self._client().delete(self._count(subject), self._lock(subject))  # type: ignore[attr-defined]
        except Exception as exc:
            raise _down() from exc

    def _client(self) -> object:
        if self._redis is None:
            from ar_common.valkey import valkey_client  # noqa: PLC0415

            self._redis = valkey_client(self.url, socket_connect_timeout=1, socket_timeout=1)
        return self._redis

    @staticmethod
    def _count(subject: str) -> str:
        return f"ar:lockout:count:{subject}"

    @staticmethod
    def _lock(subject: str) -> str:
        return f"ar:lockout:until:{subject}"


def _down() -> UnavailableError:
    return UnavailableError("login lockout is unavailable")
