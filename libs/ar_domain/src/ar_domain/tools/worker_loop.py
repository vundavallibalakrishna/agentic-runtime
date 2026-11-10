"""One model call or one tool call, saved on the run so the next activity can resume.

The checkpoint key is ``worker_loop``. Workflow history carries the run id only.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from typing import Any


class LoopLocals(TypedDict):
    messages: list[dict[str, object]]
    steps: int
    used_calls: int
    tokens: int
    tokens_in_total: int
    tokens_out_total: int
    prompt_seen: int
    cost: int
    previews: list[dict[str, object]]
    user_text: str
    repairs: int
    consecutive_errors: int
    planned: bool
    failed_open: bool
    started: float


def worker_loop_open(run: dict[str, object]) -> bool:
    """True once a previous activity saved a step to resume."""
    state = read_worker_loop(run)
    if state is None:
        return False
    messages = state.get("messages")
    return bool(state.get("opened")) or (isinstance(messages, list) and bool(messages))


def read_worker_loop(run: dict[str, object]) -> dict[str, object] | None:
    raw = run.get("checkpoint")
    if not isinstance(raw, dict):
        return None
    state = raw.get("worker_loop")
    return dict(state) if isinstance(state, dict) else None


def write_worker_loop(run: dict[str, object], state: dict[str, object]) -> None:
    raw = run.get("checkpoint")
    checkpoint = dict(raw) if isinstance(raw, dict) else {}
    checkpoint["worker_loop"] = state
    run["checkpoint"] = checkpoint


def snapshot(
    *,
    messages: list[dict[str, object]],
    steps: int,
    used_calls: int,
    tokens: int,
    tokens_in: int,
    tokens_out: int,
    prompt_seen: int,
    cost: int,
    previews: list[dict[str, object]],
    elapsed_s: float,
    user_text: str,
    repairs: int,
    consecutive_errors: int,
    planned: bool,
    failed_open: bool,
    phase: str,
    pending_calls: list[object] | None = None,
    pending_index: int = 0,
    batch_images: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """The fields the next activity needs. No prompt text beyond the message list."""
    return {
        "opened": True,
        "phase": phase,
        "messages": messages,
        "steps": steps,
        "used_calls": used_calls,
        "tokens": tokens,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "prompt_seen": prompt_seen,
        "cost": cost,
        "previews": previews,
        "elapsed_s": elapsed_s,
        "user_text": user_text,
        "repairs": repairs,
        "consecutive_errors": consecutive_errors,
        "planned": planned,
        "failed_open": failed_open,
        "pending_calls": list(pending_calls or []),
        "pending_index": pending_index,
        "batch_images": list(batch_images or []),
    }


def apply_worker_loop(state: dict[str, object], *, now: float | None = None) -> LoopLocals:
    """Locals for a resumed turn. ``started`` is a monotonic clock value."""
    messages = state.get("messages")
    previews = state.get("previews")
    moment = time.monotonic() if now is None else now
    elapsed = state.get("elapsed_s")
    try:
        elapsed_s = float(elapsed)  # type: ignore[arg-type]
    except TypeError, ValueError:
        elapsed_s = 0.0
    applied: LoopLocals = {
        "messages": [item for item in messages if isinstance(item, dict)]
        if isinstance(messages, list)
        else [],
        "steps": _int(state.get("steps")),
        "used_calls": _int(state.get("used_calls")),
        "tokens": _int(state.get("tokens")),
        "tokens_in_total": _int(state.get("tokens_in")),
        "tokens_out_total": _int(state.get("tokens_out")),
        "prompt_seen": _int(state.get("prompt_seen")),
        "cost": _int(state.get("cost")),
        "previews": [item for item in previews if isinstance(item, dict)]
        if isinstance(previews, list)
        else [],
        "user_text": str(state.get("user_text") or ""),
        "repairs": _int(state.get("repairs")),
        "consecutive_errors": _int(state.get("consecutive_errors")),
        "planned": bool(state.get("planned")),
        "failed_open": bool(state.get("failed_open")),
        "started": moment - elapsed_s,
    }
    return applied


async def consume_one_tool(  # noqa: PLR0911, PLR0912, PLR0915
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    state: dict[str, object],
    *,
    by_name: dict[str, dict[str, object]],
    limits: dict[str, int],
    alias: str,
    deferred: bool,
    openai_tools: list[dict[str, object]],
    offered: set[str],
) -> str:
    """Execute the next saved tool call. Return ``tools``, ``model``, ``paused`` or ``final``."""
    from ar_common.offload import run_sync  # noqa: PLC0415
    from ar_domain.orchestration.engine import ORCHESTRATION_NAMES, handle_orchestration  # noqa: PLC0415
    from ar_domain.tools.agent_loop import (  # noqa: PLC0415
        _act,
        _stop_budget,
        _stop_error,
        _time_left,
    )
    from ar_domain.tools.images import build_image_message  # noqa: PLC0415

    calls = state.get("pending_calls")
    pending = [item for item in calls if isinstance(item, dict)] if isinstance(calls, list) else []
    index = _int(state.get("pending_index"))
    messages = state.get("messages")
    if not isinstance(messages, list):
        messages = []
        state["messages"] = messages
    started = time.monotonic() - _float(state.get("elapsed_s"))
    if index >= len(pending):
        state["phase"] = "model"
        state["pending_calls"] = []
        state["pending_index"] = 0
        return "model"
    call = pending[index]
    used = _int(state.get("used_calls"))
    if used >= limits["max_tool_calls"]:
        _stop_budget(store, run, assistant, "max_tool_calls")
        return "final"
    used += 1
    state["used_calls"] = used
    name = str(call.get("name") or "")
    outcome: dict[str, object] | None
    if name in ORCHESTRATION_NAMES:
        loop_state = {
            "messages": messages,
            "steps": _int(state.get("steps")),
            "tokens": _int(state.get("tokens")),
            "tokens_in": _int(state.get("tokens_in")),
            "tokens_out": _int(state.get("tokens_out")),
            "cost": _int(state.get("cost")),
            "used_calls": used,
            "previews": state.get("previews") or [],
            "started": started,
            "user_text": state.get("user_text") or "",
            "limits": limits,
        }
        outcome = await handle_orchestration(store, run, assistant, call, loop_state)
        if outcome is None:
            run["step_kind"] = "paused"
            return "paused"
        if outcome.get("stop"):
            return "final"
    else:
        from ar_domain.tools.agent_loop import _invalid_args, _schema_outcome  # noqa: PLC0415

        invalid = _invalid_args(by_name.get(name), call)
        if invalid:
            outcome = _schema_outcome(call, name, invalid, used)
        else:
            outcome = await run_sync(
                _act,
                store,
                run,
                assistant,
                call,
                by_name,
                used,
                retry=_int(state.get("consecutive_errors")) > 0,
                limit_s=_time_left(limits, started),
            )
    if outcome is None:
        run["step_kind"] = "paused"
        return "paused"
    failed = bool(outcome.get("failed"))
    state["failed_open"] = failed
    errors = _int(state.get("consecutive_errors"))
    state["consecutive_errors"] = errors + 1 if failed else 0
    preview = outcome.get("preview")
    previews = state.get("previews")
    if not isinstance(previews, list):
        previews = []
        state["previews"] = previews
    if isinstance(preview, dict):
        previews.append(preview)
    messages.append(
        {
            "role": "tool",
            "tool_call_id": str(call.get("id") or ""),
            "content": str(outcome.get("wrapped") or ""),
        }
    )
    produced = outcome.get("images")
    batch = state.get("batch_images")
    if not isinstance(batch, list):
        batch = []
        state["batch_images"] = batch
    if isinstance(produced, list):
        batch.extend(item for item in produced if isinstance(item, dict))
    if deferred:
        from ar_domain.tools.agent_loop import _SEARCH_TOOL_NAMES, _add_found_tools  # noqa: PLC0415

        if name in _SEARCH_TOOL_NAMES:
            _add_found_tools(outcome.get("structured"), by_name, openai_tools, offered)
    state["elapsed_s"] = time.monotonic() - started
    state["pending_index"] = index + 1
    from ar_domain.loop.repair import tool_failure_limit  # noqa: PLC0415
    from ar_domain.tools.agent_loop import _definition  # noqa: PLC0415

    if _int(state.get("consecutive_errors")) >= tool_failure_limit(_definition(store, run)):
        _stop_error(store, run, assistant, "The tool kept failing, so this run stopped.")
        return "final"
    if index + 1 < len(pending):
        state["phase"] = "tools"
        return "tools"
    if batch:
        shown = await run_sync(
            build_image_message,
            store,
            run,
            batch,
            alias=alias,
            limit_s=_time_left(limits, started),
        )
        if isinstance(shown, dict):
            messages.append(shown)
        state["batch_images"] = []
    state["phase"] = "model"
    state["pending_calls"] = []
    state["pending_index"] = 0
    return "model"


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return 0.0
