"""Start and signal the one agent-run workflow.

Every chat, external, and research entry point builds this payload and starts
``AgentRunWorkflow`` (``run-{run_id}`` on ``ar-runtime``). The workflow runs one
activity per step. A process with no Temporal client does not run the turn.
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
    """What the worker needs. Step caps come from the run budget and install settings.

    ``max_steps`` here is how many activities the workflow may run, not the budget's count
    of model calls: see ``_max_steps``.
    """
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

    A missing client, or a workflow that is not running, returns False. The caller
    starts the run workflow. Nothing is executed in this process.
    """
    client = getattr(store, "temporal_client", None)
    handle_for = getattr(client, "get_workflow_handle", None)
    if not callable(handle_for):
        return False
    handle = handle_for(workflow_id(run_id))
    signal = getattr(handle, "signal", None)
    if not callable(signal):
        return False

    async def _send() -> bool:
        try:
            await signal(name, payload)
        except Exception as exc:
            if _workflow_missing(exc):
                return False
            raise
        return True

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return bool(asyncio.run(_send()))
    task = loop.create_task(_send())
    tasks = getattr(store, "tasks", None)
    if isinstance(tasks, list):
        tasks.append(task)
    return True


def continue_on_worker(
    store: object,
    run_id: uuid.UUID,
    text: str,
    decision: dict[str, object] | None = None,
) -> None:
    """Start ``AgentRunWorkflow`` for a run that is not already executing.

    A running loop schedules the start. A synchronous caller waits for the worker.
    ``decision`` is the approval or input the first activity applies.
    """
    start = getattr(store, "_start_turn", None)
    if not callable(start):
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(start(run_id, text, [], decision=decision))
        return
    task = loop.create_task(start(run_id, text, [], decision=decision))
    tasks = getattr(store, "tasks", None)
    if isinstance(tasks, list):
        tasks.append(task)


def _workflow_missing(exc: BaseException) -> bool:
    status = getattr(exc, "status", None)
    name = getattr(status, "name", "")
    if name in {"NOT_FOUND", "NOT_FOUND_STATUS"}:
        return True
    text = str(exc).lower()
    return "not found" in text or "workflow execution already completed" in text


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
    # The workflow counts activities, and a model call and a tool call are one each. The
    # budget counts them apart: max_steps model calls and max_tool_calls tool calls, and a
    # tool call that waits for approval takes one more activity to resume. The loop stops
    # the run on its own budget and says which limit was reached; this is the outer bound
    # that lets it get there.
    return max(1, int(budget["max_steps"]) + 2 * int(budget["max_tool_calls"]))


def _setting(name: str, default: int) -> int:
    from ar_common.settings import get_settings  # noqa: PLC0415

    raw = getattr(get_settings(), name, default)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return default
    return max(1, raw)
