"""What the caller asked of one turn. Stored on the run, so any worker reads it.

A turn option kept as a loose field on the in-memory run is gone when another process
loads the run from the database. These two functions are the only way to set and read one.
"""

from __future__ import annotations

OPTIONS = frozenset(
    {
        "response_format",
        "suggest_followups",
        "orchestration_child",
        "waits",
        "agent_chain",
        "budget",
        "pool",
        "permissions",
        "task_template",
        "items",
        "collection_ids",
        "file_ids",
    }
)


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


def permissions_of(run: dict[str, object]) -> list[str] | None:
    """The caller's effective permissions, including after a reload.

    A loose field is enough in the process that created the run. The copy kept
    on ``request`` is what another process reads back from the database.
    """
    direct = run.get("permissions")
    if isinstance(direct, list | tuple):
        return [str(item) for item in direct]
    stored = asked(run, "permissions")
    if isinstance(stored, list | tuple):
        return [str(item) for item in stored]
    return None


def cannot_wait(run: dict[str, object]) -> bool:
    """Whether this run was called by another agent in a way that cannot wait for a person.

    A called agent that is its own workflow waits like any run: its caller's workflow
    waits for it. One run inside its caller's step has nobody to wait for.
    """
    return bool(asked(run, "orchestration_child")) and not asked(run, "waits")
