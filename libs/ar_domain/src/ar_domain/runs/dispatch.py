"""Start and signal the one agent-run workflow.

Every chat, external, and research entry point builds this payload and starts
``AgentRunWorkflow`` (``run-{run_id}`` on ``ar-runtime``). The workflow runs one
activity per step. A process with no Temporal client does not invent a second
runner here: the caller keeps the existing dev fallback.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

_QUEUE = "ar-runtime"


def workflow_id(run_id: object) -> str:
    """Temporal workflow id for a run. Callers do not mint a second id."""
    return f"run-{run_id}"


def workflow_payload(store: object, run: object, run_id: uuid.UUID, text: str) -> dict[str, object]:
    """What the worker needs. Step caps come from the run budget and install settings."""
    payload: dict[str, object] = {
        "run_id": str(run_id),
        "steps": True,
        "text": text,
        "max_steps": _max_steps(store, run, text),
        "history_steps": _setting("run_history_steps", 24),
        "wait_s": _setting("approval_wait_s", 86400),
    }
    return payload


def request_signal(store: object, run_id: uuid.UUID, name: str, payload: dict[str, object]) -> bool:
    """Signal ``run-{id}``. True when a client accepted the signal (or will).

    A missing client returns False so the caller can follow the no-worker path.
    The signal is sent on the running loop and does not block the request.
    """
    client = getattr(store, "temporal_client", None)
    handle_for = getattr(client, "get_workflow_handle", None)
    if not callable(handle_for):
        return False
    handle = handle_for(workflow_id(run_id))
    signal = getattr(handle, "signal", None)
    if not callable(signal):
        return False

    async def _send() -> None:
        await signal(name, payload)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_send())
        return True
    task = loop.create_task(_send())
    tasks = getattr(store, "tasks", None)
    if isinstance(tasks, list):
        tasks.append(task)
    return True


def _max_steps(store: object, run: object, text: str) -> int:
    if isinstance(run, dict) and run.get("trigger") == "research":
        from ar_domain.research.engine import max_steps, state_of  # noqa: PLC0415

        return max(1, max_steps(state_of(run, text)))
    definition: dict[str, object] = {}
    if isinstance(run, dict):
        versions = getattr(store, "versions", {})
        version = versions.get(run.get("agent_version_id")) if isinstance(versions, dict) else None
        raw = version.get("definition") if isinstance(version, dict) else None
        if isinstance(raw, dict):
            definition = raw
    from ar_domain.tools.agent_loop import read_budget  # noqa: PLC0415

    budget = read_budget(definition, run if isinstance(run, dict) else None)
    return max(1, int(budget["max_steps"]))


def _setting(name: str, default: int) -> int:
    from ar_common.settings import get_settings  # noqa: PLC0415

    raw = getattr(get_settings(), name, default)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return default
    return max(1, raw)
