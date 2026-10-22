"""Dedupe keys and socket-mode leader locks.

Valkey is the production store (`ar:chan:dedupe:*`, `ar:chan:leader:*`).
This process map is the stand-in when `AR_VALKEY_URL` is empty (OQ-42).
"""


class Dedupe:
    def __init__(self) -> None:
        self.seen: dict[str, float] = {}

    def once(self, key: str, now: float, ttl: float = 3600) -> bool:
        expiry = self.seen.get(key)
        if expiry is not None and expiry > now:
            return False
        self.seen[f"ar:chan:dedupe:{key}"] = now + ttl
        self.seen[key] = now + ttl
        return True


class LeaderLock:
    def __init__(self) -> None:
        self.held: dict[str, float] = {}

    def acquire(self, integration_id: str, now: float, ttl: float = 30) -> bool:
        key = f"ar:chan:leader:{integration_id}"
        current = self.held.get(key)
        if current is not None and current > now:
            return False
        self.held[key] = now + ttl
        return True

    def renew(self, integration_id: str, now: float, ttl: float = 30) -> bool:
        key = f"ar:chan:leader:{integration_id}"
        if key not in self.held:
            return False
        self.held[key] = now + ttl
        return True
