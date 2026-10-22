"""Stable ids for the dev tenant. Memory and Postgres share them after M10."""

import uuid

DEMO_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def demo_id(name: str) -> uuid.UUID:
    """Stable id for one dev catalogue row."""
    return uuid.uuid5(DEMO_NS, f"ar-dev-{name}")
