"""Notification fan-out decisions. Spec: docs/03-specs/20-notifications-events.md §2."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Notice:
    kind: str
    title: str
    body: str
    email: str | None


def notices_for(topic: str, payload: dict[str, object]) -> list[Notice]:
    """Map a domain event onto in-app and email notices."""
    if topic == "invitation.created":
        email = str(payload.get("email", ""))
        return [Notice("system", "You are invited", f"Invitation for {email}", email or None)]
    if topic == "approval.requested":
        return [Notice("approval_requested", "Approval requested", "A run is waiting", None)]
    return []
