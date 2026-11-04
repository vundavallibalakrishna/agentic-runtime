"""Tools the live model uses to call agents, hand off, or ask a person."""

from __future__ import annotations

import time
from typing import Any, TypedDict

import orjson

from ar_domain.orchestration.ask import ask_person
from ar_domain.orchestration.children import definition_of, run_named, run_parallel, wrapped
from ar_domain.orchestration.spec import (
    agent_slug,
    contract_line,
    human_enabled,
    subagent_spec,
    whole,
)

ORCHESTRATION_NAMES = frozenset({"agents_call", "agents_parallel", "agents_handoff", "agents_ask"})


def orchestration_tools(
    store: Any, run: dict[str, object], definition: dict[str, object]
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    """OpenAI tool definitions plus the lookup rows the loop expects."""
    if not isinstance(run.get("agent_chain"), list):
        slug = agent_slug(store, run)
        run["agent_chain"] = [slug] if slug else []
    spec = subagent_spec(definition)
    names = list(spec["allowed"])
    current = agent_slug(store, run)
    if spec["allow_self_clone"] and current and current not in names:
        names.append(current)
    tools: list[dict[str, object]] = []
    index: dict[str, dict[str, object]] = {}
    if names:
        lines = [contract_line(store, run.get("tenant_id"), name) for name in spec["allowed"]]
        if spec["allow_self_clone"] and current:
            lines.append(f"{current}: a copy of this agent with the same instructions.")
        description = "Call one agent and wait for its answer. " + " ".join(lines)
        _add(tools, index, "agents_call", description, _call_schema(names))
        _add(
            tools,
            index,
            "agents_parallel",
            "Call several agents at once and return every answer so you can combine them. "
            + " ".join(lines),
            _parallel_schema(names, spec["max_parallel"]),
        )
        _add(
            tools,
            index,
            "agents_handoff",
            "Hand this conversation to another agent. You stop after the handoff. "
            + " ".join(lines),
            _call_schema(names),
        )
    if human_enabled(definition):
        _add(
            tools,
            index,
            "agents_ask",
            "Pause until a person answers. kind=approval cannot be assigned to the requester. "
            "The run resumes with the answer.",
            {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "kind": {"type": "string", "enum": ["question", "approval"]},
                    "assignee_user_id": {"type": "string"},
                },
                "required": ["question"],
            },
        )
    return tools, index


async def handle_orchestration(
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    call: dict[str, object],
    state: dict[str, object],
) -> dict[str, object] | None:
    """Run one orchestration tool. None means the run is paused for a person."""
    name = str(call.get("name") or "")
    arguments = call.get("arguments")
    payload = arguments if isinstance(arguments, dict) else {}
    call_id = str(call.get("id") or "call")
    state["elapsed_s"] = _elapsed(state)
    if name == "agents_ask":
        problem = ask_person(store, run, assistant, payload, call_id)
        if problem is None:
            return None
        return _done(name, call_id, str(problem.get("text") or ""), failed=True)
    if name == "agents_parallel":
        calls = payload.get("calls")
        rows = [item for item in calls if isinstance(item, dict)] if isinstance(calls, list) else []
        outcome = await run_parallel(store, run, rows, state)
        raw_results = outcome.get("results")
        items = raw_results if isinstance(raw_results, list) else []
        body = {"results": [_public(item) for item in items if isinstance(item, dict)]}
        return _done(
            name,
            call_id,
            orjson.dumps(body).decode(),
            failed=bool(outcome.get("failed")),
            tokens=whole(outcome.get("tokens"), 0),
            cost=whole(outcome.get("cost"), 0),
        )
    slug = str(payload.get("agent") or "")
    task = str(payload.get("task") or payload.get("note") or "")
    outcome = await run_named(store, run, slug, task, state)
    text = str(outcome.get("text") or "")
    if name == "agents_handoff" and not outcome.get("failed"):
        return {
            "failed": False,
            "stop": True,
            "answer": text,
            "tokens": whole(outcome.get("tokens"), 0),
            "cost": whole(outcome.get("cost"), 0),
            "preview": _preview(name, "completed", text),
            "wrapped": wrapped(name, call_id, text),
        }
    return _done(
        name,
        call_id,
        text,
        failed=bool(outcome.get("failed")),
        tokens=whole(outcome.get("tokens"), 0),
        cost=whole(outcome.get("cost"), 0),
    )


def _elapsed(state: dict[str, object]) -> int:
    started = state.get("started")
    if isinstance(started, int | float) and not isinstance(started, bool):
        return int(time.monotonic() - float(started))
    return 0


def save_checkpoint(run: dict[str, object], state: dict[str, object], call_id: str) -> None:
    elapsed = _elapsed(state)
    run["checkpoint"] = {
        "messages": state.get("messages") or [],
        "steps": state.get("steps") or 0,
        "tokens": state.get("tokens") or 0,
        "cost": state.get("cost") or 0,
        "used_calls": state.get("used_calls") or 0,
        "previews": state.get("previews") or [],
        "pending_call_id": call_id,
        "elapsed_s": elapsed,
        "user_text": state.get("user_text") or "",
        "resumable": True,
    }


class RestoredRun(TypedDict):
    messages: list[dict[str, object]]
    steps: int
    tokens: int
    cost: int
    used_calls: int
    previews: list[dict[str, object]]
    elapsed_s: int
    user_text: str


def restore_checkpoint(run: dict[str, object]) -> RestoredRun | None:
    """Continue a paused run. The person's answer is appended as the tool result."""
    if run.get("resume") is not True:
        return None
    raw = run.get("checkpoint")
    if not isinstance(raw, dict) or not isinstance(raw.get("messages"), list):
        return None
    raw_messages = raw.get("messages")
    messages = (
        [item for item in raw_messages if isinstance(item, dict)]
        if isinstance(raw_messages, list)
        else []
    )
    answer = str(run.get("resume_answer") or "")
    call_id = str(raw.get("pending_call_id") or "ask")
    messages.append(
        {
            "role": "tool",
            "tool_call_id": call_id,
            "content": wrapped("agents_ask", call_id, f"The person answered: {answer}"),
        }
    )
    run["resume"] = False
    run["resume_answer"] = None
    raw_previews = raw.get("previews")
    previews = (
        [item for item in raw_previews if isinstance(item, dict)]
        if isinstance(raw_previews, list)
        else []
    )
    return {
        "messages": messages,
        "steps": whole(raw.get("steps"), 0),
        "tokens": whole(raw.get("tokens"), 0),
        "cost": whole(raw.get("cost"), 0),
        "used_calls": whole(raw.get("used_calls"), 0),
        "previews": previews,
        "elapsed_s": whole(raw.get("elapsed_s"), 0),
        "user_text": str(raw.get("user_text") or ""),
    }


async def resume_run(store: Any, run_id: object) -> None:
    run = store.runs.get(run_id)
    if not isinstance(run, dict):
        return
    assistant_id = run.get("assistant_message_id")
    assistant = store.messages.get(assistant_id)
    if not isinstance(assistant, dict):
        return
    from ar_domain.tools.agent_loop import run_agent_loop  # noqa: PLC0415

    await run_agent_loop(store, run, assistant, str(run.get("user_text") or ""))


def _add(
    tools: list[dict[str, object]],
    index: dict[str, dict[str, object]],
    name: str,
    description: str,
    parameters: dict[str, object],
) -> None:
    row = {
        "model_name": name,
        "qualified_name": name,
        "description": description,
        "parameters": parameters,
        "risk_class": "R0",
        "orchestration": True,
    }
    index[name] = row
    tools.append(
        {
            "type": "function",
            "function": {"name": name, "description": description, "parameters": parameters},
        }
    )


def _call_schema(names: list[str]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "agent": {"type": "string", "enum": names},
            "task": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["agent"],
    }


def _parallel_schema(names: list[str], cap: int) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "calls": {
                "type": "array",
                "maxItems": cap,
                "items": {
                    "type": "object",
                    "properties": {
                        "agent": {"type": "string", "enum": names},
                        "task": {"type": "string"},
                    },
                    "required": ["agent", "task"],
                },
            }
        },
        "required": ["calls"],
    }


def _done(
    name: str,
    call_id: str,
    text: str,
    *,
    failed: bool,
    tokens: int = 0,
    cost: int = 0,
) -> dict[str, object]:
    return {
        "failed": failed,
        "stop": False,
        "tokens": tokens,
        "cost": cost,
        "preview": _preview(name, "failed" if failed else "completed", text),
        "wrapped": wrapped(name, call_id, text),
    }


def _preview(name: str, status: str, text: str) -> dict[str, object]:
    return {"qualified_name": name, "status": status, "result_preview": text[:500]}


def _public(item: dict[str, object]) -> dict[str, object]:
    return {
        "agent": item.get("agent"),
        "status": item.get("status"),
        "answer": item.get("text"),
        "child_run_id": item.get("child_id"),
        "code": item.get("code"),
    }


def remember_parent_definition(store: Any, run: dict[str, object]) -> dict[str, object]:
    return definition_of(store, run)
