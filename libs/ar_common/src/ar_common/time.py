"""UTC clock. Spec: docs/08-quality/coding-standards-python.md §2."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(UTC)
