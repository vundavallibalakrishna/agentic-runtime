"""The tool call a run is waiting to have approved, kept on the run's checkpoint.

The checkpoint is stored with the run, so any process can continue the run when someone
decides: the API request that takes the decision is not the process that paused it.
"""

from __future__ import annotations

import uuid

_KEY = "pending_approval"
_IDS = ("approval_id", "tool_version_id", "tool_call_id", "model_call_id")


def hold(run: dict[str, object], pending: dict[str, object]) -> None:
    """Record what the run waits on. Ids are written as text, so the checkpoint is JSON."""
    raw = run.get("checkpoint")
    checkpoint = dict(raw) if isinstance(raw, dict) else {}
    checkpoint[_KEY] = {
        key: str(value) if isinstance(value, uuid.UUID) else value for key, value in pending.items()
    }
    run["checkpoint"] = checkpoint


def held(run: object) -> dict[str, object] | None:
    """What the run waits on, with its ids as ids again. ``None`` when it waits on nothing."""
    raw = run.get("checkpoint") if isinstance(run, dict) else None
    stored = raw.get(_KEY) if isinstance(raw, dict) else None
    if not isinstance(stored, dict):
        return None
    pending: dict[str, object] = dict(stored)
    for key in _IDS:
        try:
            pending[key] = uuid.UUID(str(pending[key]))
        except KeyError, ValueError:
            continue
    return pending


def amend(run: dict[str, object], **changes: object) -> None:
    """Change fields of what the run waits on. Nothing happens when it waits on nothing."""
    pending = held(run)
    if pending is not None:
        hold(run, {**pending, **changes})


def release(run: dict[str, object]) -> None:
    """The run no longer waits on an approval."""
    raw = run.get("checkpoint")
    if isinstance(raw, dict) and _KEY in raw:
        run["checkpoint"] = {key: value for key, value in raw.items() if key != _KEY}
