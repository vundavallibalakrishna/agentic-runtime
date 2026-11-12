"""What the caller asked of one turn. Stored on the run, so any worker reads it.

A turn option kept as a loose field on the in-memory run is gone when another process
loads the run from the database. These two functions are the only way to set and read one.
"""

from __future__ import annotations

OPTIONS = frozenset({"response_format", "suggest_followups", "orchestration_child"})


def ask(run: dict[str, object], name: str, value: object) -> None:
    """Record one option of the turn's request."""
    if name not in OPTIONS:
        message = f"unknown turn option {name}"
        raise ValueError(message)
    current = run.get("request")
    request = dict(current) if isinstance(current, dict) else {}
    request[name] = value
    run["request"] = request


def asked(run: dict[str, object], name: str) -> object:
    """The option's value, or None when the turn did not ask for it."""
    current = run.get("request")
    return current.get(name) if isinstance(current, dict) else None
