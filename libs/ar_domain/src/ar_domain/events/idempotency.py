"""Idempotency decisions. Spec: docs/03-specs/20-notifications-events.md §4."""

from dataclasses import dataclass
from typing import Literal

DecisionKind = Literal["store", "replay", "reused", "in_flight"]


@dataclass(frozen=True, slots=True)
class StoredResponse:
    request_hash: str
    status_code: int | None
    body: bytes | None


@dataclass(frozen=True, slots=True)
class IdempotencyDecision:
    kind: DecisionKind
    status_code: int | None = None
    body: bytes | None = None


def decide(stored: StoredResponse | None, request_hash: str) -> IdempotencyDecision:
    """Compare a new request with the stored key, if any."""
    if stored is None:
        return IdempotencyDecision(kind="store")
    if stored.request_hash != request_hash:
        return IdempotencyDecision(kind="reused")
    if stored.status_code is None:
        return IdempotencyDecision(kind="in_flight")
    return IdempotencyDecision(kind="replay", status_code=stored.status_code, body=stored.body)
