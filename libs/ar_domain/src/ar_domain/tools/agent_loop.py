"""Plan, act, check and retry. Spec: docs/03-specs/07-agent-runtime.md.

A fake provider leaves the turn on the existing path. A real provider, or a
test that marks the call real, owns the turn: the model sees tool results,
a failed call is sent back for another attempt, and every step is traced.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_common.wrapping import wrap_tool_result
from ar_domain.runs.logic import budget_exceeded
from ar_domain.tools.logic import call_args_hash
from ar_domain.tools.pipeline import ToolPipeline

if TYPE_CHECKING:
    from typing import Any

_GUIDE = (
    "Plan the work, then act. Inspect each tool result before you answer. "
    "If a tool call fails, read the error and call it again with corrected arguments. "
    "Do not claim a tool succeeded when it failed. "
    "Calls that send, delete, spend or change stored data wait for approval."
)


def model_alias_for(store: Any, run: dict[str, object]) -> str:
    """Conversation choice, then the agent alias, then reasoning."""
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        chosen = conversation.get("model_alias")
        if isinstance(chosen, str) and chosen.strip():
            return chosen.strip()
    version = store.versions.get(run.get("agent_version_id"))
    definition = version.get("definition") if isinstance(version, dict) else None
    model = definition.get("model") if isinstance(definition, dict) else None
    if isinstance(model, dict):
        alias = model.get("alias")
        if isinstance(alias, str) and alias.strip():
            return alias.strip()
    return "reasoning"


def read_budget(definition: dict[str, object]) -> dict[str, int]:
    """Customer limits, with the platform defaults for anything omitted."""
    raw = definition.get("budget")
    source = raw if isinstance(raw, dict) else {}
    defaults = {
        "max_steps": 8,
        "max_tokens": 16000,
        "max_cost_micros": 1_000_000,
        "max_wall_clock_s": 120,
        "max_tool_calls": 8,
    }
    limits: dict[str, int] = {}
    for key, default in defaults.items():
        value = source.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            limits[key] = default
        else:
            limits[key] = value
    return limits


async def run_agent_loop(  # noqa: PLR0911, PLR0912, PLR0915
    store: Any, run: dict[str, object], assistant: dict[str, object], user_text: str
) -> bool:
    """Run the model loop. Return false when a fake provider should answer alone."""
    definition = _definition(store, run)
    if definition is None:
        return False
    limits = read_budget(definition)
    if limits["max_tool_calls"] <= 0:
        return False
    alias = model_alias_for(store, run)
    _model, _headers, _timeout, real = store._completion_call(
        uuid.UUID(str(run["tenant_id"])), alias
    )
    if not real:
        return False
    version_id = run.get("agent_version_id")
    user_id = run.get("user_id")
    if not isinstance(version_id, uuid.UUID) or not isinstance(user_id, uuid.UUID):
        return False
    catalog = ToolPipeline(store).resolve_catalog(agent_version_id=version_id, user_id=user_id)
    raw_tools = catalog.get("tools")
    tools = (
        [row for row in raw_tools if isinstance(row, dict)] if isinstance(raw_tools, list) else []
    )
    if not tools:
        return False
    by_name = _index(tools)
    openai_tools = [_openai_tool(row) for row in tools]
    instructions = str(definition.get("instructions") or "Help.")
    messages: list[dict[str, object]] = [
        {"role": "system", "content": f"{instructions}\n\n{_GUIDE}"},
        {"role": "user", "content": user_text},
    ]
    started = time.monotonic()
    steps = 0
    used_calls = 0
    tokens = 0
    cost = 0
    consecutive_errors = 0
    planned = False
    failed_open = False
    previews: list[dict[str, object]] = []
    while True:
        steps += 1
        limit = _over(limits, steps, tokens, cost, started, used_calls)
        if limit is not None:
            _stop_budget(store, run, assistant, limit)
            return True
        turn = await store.complete_turn(
            messages,
            openai_tools,
            tenant_id=uuid.UUID(str(run["tenant_id"])),
            model_alias=alias,
        )
        if not isinstance(turn, dict):
            _stop_error(store, run, assistant, "The model provider did not answer.")
            return True
        raw_usage = turn.get("usage")
        usage = raw_usage if isinstance(raw_usage, dict) else {}
        tokens_in = usage.get("tokens_in")
        tokens_out = usage.get("tokens_out")
        tokens += int(tokens_in or 0) + int(tokens_out or 0)
        cost += int(tokens_out or 1)
        calls = turn.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            answer = str(turn.get("text") or "").strip() or "The model returned an empty answer."
            answer = _checked(store, run, answer, failed_open=failed_open, tool_calls=used_calls)
            _finish(store, run, assistant, answer, previews)
            return True
        if not planned:
            _plan(store, run, calls)
            planned = True
        messages.append({"role": "assistant", "content": None, "tool_calls": _wire_calls(calls)})
        for call in calls:
            if not isinstance(call, dict):
                continue
            if used_calls >= limits["max_tool_calls"]:
                _stop_budget(store, run, assistant, "max_tool_calls")
                return True
            used_calls += 1
            outcome = _act(
                store,
                run,
                assistant,
                call,
                by_name,
                used_calls,
                retry=consecutive_errors > 0,
            )
            if outcome is None:
                return True
            failed = bool(outcome["failed"])
            failed_open = failed
            consecutive_errors = consecutive_errors + 1 if failed else 0
            preview = outcome["preview"]
            if isinstance(preview, dict):
                previews.append(preview)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(call.get("id") or ""),
                    "content": str(outcome["wrapped"]),
                }
            )
            if consecutive_errors >= 8:
                _stop_error(
                    store,
                    run,
                    assistant,
                    "The tool kept failing, so this run stopped.",
                )
                return True


def _definition(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    version = store.versions.get(run.get("agent_version_id"))
    definition = version.get("definition") if isinstance(version, dict) else None
    if not isinstance(definition, dict):
        return None
    return definition


def _index(tools: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    found: dict[str, dict[str, object]] = {}
    for row in tools:
        model_name = str(row.get("model_name") or "")
        qualified = str(row.get("qualified_name") or "")
        if model_name:
            found[model_name] = row
        if qualified:
            found[qualified] = row
    return found


def _openai_tool(row: dict[str, object]) -> dict[str, object]:
    parameters = row.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": str(row.get("model_name") or row.get("qualified_name") or "tool"),
            "description": str(row.get("description") or ""),
            "parameters": parameters,
        },
    }


def _wire_calls(calls: list[object]) -> list[dict[str, object]]:
    import orjson  # noqa: PLC0415

    wired: list[dict[str, object]] = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            continue
        arguments = call.get("arguments")
        payload = arguments if isinstance(arguments, dict) else {}
        wired.append(
            {
                "id": str(call.get("id") or f"call_{index}"),
                "type": "function",
                "function": {
                    "name": str(call.get("name") or ""),
                    "arguments": orjson.dumps(payload).decode(),
                },
            }
        )
    return wired


def _over(  # noqa: PLR0917
    limits: dict[str, int], steps: int, tokens: int, cost: int, started: float, tool_calls: int
) -> str | None:
    return budget_exceeded(
        steps=steps,
        tokens=max(tokens, 1),
        cost_micros=cost,
        elapsed_s=int(time.monotonic() - started),
        tool_calls=tool_calls,
        budget=limits,
    )


def _plan(store: Any, run: dict[str, object], calls: list[object]) -> None:
    items = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            continue
        name = str(call.get("name") or "tool").replace("__", ".")
        items.append({"id": str(index + 1), "title": name, "status": "in_progress"})
    if not items:
        return
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["plan"] = [str(item["title"]) for item in items]
    store._emit(run, "plan.updated", {"items": items})
    _audit(store, run, "run.planned", str(run.get("id")), {"count": len(items)})


def _act(  # noqa: PLR0917
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    call: dict[str, object],
    by_name: dict[str, dict[str, object]],
    attempt: int,
    *,
    retry: bool,
) -> dict[str, object] | None:
    name = str(call.get("name") or "")
    bound = by_name.get(name)
    arguments = call.get("arguments")
    payload = arguments if isinstance(arguments, dict) else {}
    model_call_id = str(call.get("id") or f"call_{attempt}")
    if bound is None:
        preview = {
            "qualified_name": name,
            "status": "failed",
            "result_preview": "That tool is not available to this agent.",
            "attempt": attempt,
        }
        store._emit(
            run,
            "tool_call.failed",
            {
                "tool_call_id": model_call_id,
                "qualified_name": name,
                "status": "failed",
                "attempt": attempt,
                "error": {"code": "not_found", "message": preview["result_preview"]},
            },
        )
        _audit(
            store,
            run,
            "tool.called",
            model_call_id,
            {"status": "failed", "attempt": attempt},
            outcome="failure",
        )
        return {
            "failed": True,
            "preview": preview,
            "wrapped": wrap_tool_result(
                tool=name or "tool",
                call_id=model_call_id,
                content="That tool is not available to this agent.",
            ),
        }
    qualified = str(bound.get("qualified_name") or name)
    version_id = uuid.UUID(str(bound["tool_version_id"]))
    digest = call_args_hash(str(version_id), payload)
    store._emit(
        run,
        "tool_call.started",
        {
            "tool_call_id": model_call_id,
            "model_call_id": model_call_id,
            "qualified_name": qualified,
            "title": qualified,
            "risk_class": bound.get("risk_class"),
            "attempt": attempt,
        },
    )
    result = ToolPipeline(store).execute(
        {
            "tenant_id": run.get("tenant_id"),
            "user_id": run.get("user_id"),
            "run_id": run.get("id"),
            "agent_id": run.get("agent_id"),
            "agent_version_id": run.get("agent_version_id"),
            "tool_version_id": version_id,
            "arguments": payload,
            "args_hash": digest,
            "model_call_id": model_call_id,
        }
    )
    if result.get("status") == "awaiting_approval":
        from ar_domain.tools.chat_loop import _pause  # noqa: PLC0415

        _pause(
            store,
            run,
            assistant,
            {
                "tool_version_id": version_id,
                "qualified_name": qualified,
                "risk_class": bound.get("risk_class"),
                "arguments": payload,
            },
            result,
            payload,
        )
        return None
    failed = result.get("status") != "succeeded"
    event = "tool_call.failed" if failed else "tool_call.completed"
    error_body = result.get("error")
    store._emit(
        run,
        event,
        {
            "tool_call_id": result.get("tool_call_id") or model_call_id,
            "qualified_name": qualified,
            "status": result.get("status"),
            "result_preview": result.get("result_preview"),
            "error": error_body,
            "attempt": attempt,
            "latency_ms": result.get("latency_ms"),
        },
    )
    _audit(
        store,
        run,
        "tool.called",
        str(result.get("tool_call_id") or model_call_id),
        {"status": result.get("status"), "attempt": attempt, "args_hash": digest},
        outcome="failure" if failed else "success",
    )
    if retry:
        _audit(
            store,
            run,
            "run.retried",
            str(result.get("tool_call_id") or model_call_id),
            {"attempt": attempt},
            outcome="failure" if failed else "success",
        )
    text = str(result.get("result_preview") or "")
    if failed and isinstance(error_body, dict):
        text = str(error_body.get("message") or text)
    return {
        "failed": failed,
        "preview": {
            "qualified_name": qualified,
            "status": result.get("status"),
            "result_preview": result.get("result_preview"),
            "attempt": attempt,
            "error": error_body,
        },
        "wrapped": wrap_tool_result(tool=qualified, call_id=model_call_id, content=text or "empty"),
    }


def _checked(
    store: Any, run: dict[str, object], answer: str, *, failed_open: bool, tool_calls: int
) -> str:
    hidden = failed_open and not any(
        word in answer.lower() for word in ("fail", "error", "could not", "unable", "retry")
    )
    if hidden:
        answer = f"{answer}\n\nA tool call failed and was not recovered."
    _audit(
        store,
        run,
        "run.checked",
        str(run.get("id")),
        {"tool_calls": tool_calls, "recovered": not failed_open},
        outcome="failure" if hidden else "success",
    )
    return answer


def _finish(
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    answer: str,
    previews: list[dict[str, object]],
) -> None:
    assistant["text"] = answer
    assistant["content"] = [{"type": "text", "text": answer}]
    assistant["tool_calls"] = previews
    assistant["status"] = "completed"
    run["status"] = "completed"
    run["ended_at"] = utcnow()
    run["result_summary"] = answer[:8000]
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["active_run_id"] = None
    assistant_id = assistant.get("id")
    usage = {"tokens_in": 1, "tokens_out": max(1, len(answer.split()))}
    run["usage"] = usage
    store._emit(run, "message.completed", {"message_id": str(assistant_id), "text": answer})
    store._emit(run, "run.completed", {"final_message_id": str(assistant_id), "usage": usage})


def _stop_budget(
    store: Any, run: dict[str, object], assistant: dict[str, object], limit: str
) -> None:
    text = f"Stopped because the {limit.replace('_', ' ')} limit was reached."
    assistant["text"] = text
    assistant["content"] = [{"type": "text", "text": text}]
    assistant["status"] = "completed"
    run["status"] = "budget_exceeded"
    run["ended_at"] = utcnow()
    run["result_summary"] = text
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["active_run_id"] = None
    store._emit(run, "run.budget_exceeded", {"limit": limit})
    _audit(
        store, run, "run.budget_exceeded", str(run.get("id")), {"limit": limit}, outcome="failure"
    )


def _stop_error(
    store: Any, run: dict[str, object], assistant: dict[str, object], text: str
) -> None:
    assistant["text"] = text
    assistant["content"] = [{"type": "text", "text": text}]
    assistant["status"] = "completed"
    run["status"] = "failed"
    run["ended_at"] = utcnow()
    run["error"] = {"code": "model_error", "message": text}
    run["result_summary"] = text
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["active_run_id"] = None
    store._emit(run, "run.failed", {"error": run["error"]})


def _audit(
    store: Any,
    run: dict[str, object],
    action: str,
    target_id: str,
    detail: dict[str, object],
    *,
    outcome: str = "success",
) -> None:
    store.audit_log.append(
        {
            "tenant_id": str(run.get("tenant_id")),
            "actor_id": str(run.get("user_id")),
            "action": action,
            "target_type": "run",
            "target_id": target_id,
            "detail": detail,
            "outcome": outcome,
            "at": utcnow().isoformat(),
        }
    )
