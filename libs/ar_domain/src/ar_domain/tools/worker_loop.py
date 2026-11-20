"""One model call or one tool call, saved on the run so the next activity can resume.

The checkpoint key is ``worker_loop``. Workflow history carries the run id only.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, TypedDict

from ar_common.logging import get_logger

if TYPE_CHECKING:
    from typing import Any


_LOG = get_logger(__name__)


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
    usage_source: str


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
    usage_source: str = "",
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
        "usage_source": usage_source,
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
        "usage_source": str(state.get("usage_source") or ""),
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
        saved = state.get("previews")
        _stop_budget(
            store, run, assistant, "max_tool_calls", saved if isinstance(saved, list) else []
        )
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
            # A handoff ends this agent's turn with the other agent's answer. Without this
            # the turn was left unfinished, and the next step handed over again.
            from ar_domain.tools.agent_loop import _finish  # noqa: PLC0415

            previews = state.get("previews")
            _finish(
                store,
                run,
                assistant,
                str(outcome.get("answer") or ""),
                previews if isinstance(previews, list) else [],
            )
            return "final"
    else:
        from ar_domain.loop.repair import output_repair_limit  # noqa: PLC0415
        from ar_domain.tools.agent_loop import (  # noqa: PLC0415
            _argument_problem,
            _definition,
            _schema_outcome,
            _terminal_text,
        )

        invalid = _argument_problem(by_name.get(name), call)
        if invalid:
            # Which tool, and whether its arguments could not be read or did not fit the
            # tool's schema. The arguments and the error text can hold content, so
            # neither is logged.
            _LOG.warning(
                "tool_arguments_rejected",
                tool=name,
                problem="unreadable" if call.get("arguments_error") else "schema",
            )
            state["repairs"] = _int(state.get("repairs")) + 1
            if _int(state.get("repairs")) > output_repair_limit(_definition(store, run)):
                _stop_error(store, run, assistant, _terminal_text(), code="repair_exhausted")
                return "final"
        if invalid:
            outcome = _schema_outcome(call, name, invalid, used)
        elif _is_document_map(name) and _map_needs_activities(store, run, call):
            state["used_calls"] = used - 1
            state["pending_index"] = index
            state["phase"] = "tools"
            state["elapsed_s"] = time.monotonic() - started
            return "sections"
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
    state["failed_open"] = bool(state.get("failed_open")) or failed
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


def _is_document_map(name: str) -> bool:
    return name.replace("__", ".") == "documents.map"


def _map_needs_activities(store: Any, run: dict[str, object], call: dict[str, object]) -> bool:
    """Prepare the map and leave the sections to the workflow when any remain."""
    from ar_common.errors import ArError  # noqa: PLC0415
    from ar_domain.documents.sections import begin_map, map_ready, pending_sections  # noqa: PLC0415

    arguments = call.get("arguments")
    payload = dict(arguments) if isinstance(arguments, dict) else {}
    try:
        begin_map(store, run, payload)
    except ArError:
        return False
    if map_ready(run):
        return False
    batch = pending_sections(store, run)
    if not batch:
        return False
    run["section_batch"] = batch
    run["step_kind"] = "sections"
    return True


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return 0.0
