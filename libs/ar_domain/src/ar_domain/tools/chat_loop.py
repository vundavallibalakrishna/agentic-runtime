"""Run tool calls inside the in-process chat loop.

The dev API still advances runs in this process (OQ-31, OQ-34). The Temporal
workflow in ``ar_runtime`` is the worker path.
"""

import re
import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.tools.logic import call_args_hash
from ar_domain.tools.pipeline import ToolPipeline

if TYPE_CHECKING:
    from typing import Any

_TICKET = re.compile(r"(?i)(?:file|create)\s+a\s+ticket[:\s]+(.+)")
_ORDERS = re.compile(r"(?i)how many orders|orders are in the warehouse|count the orders")
_PET = re.compile(r"(?i)(?:create|add)\s+(?:a\s+)?pet(?:\s+named)?\s+([A-Za-z0-9][\w .'-]{0,40})")
_DELETE = re.compile(r"(?i)delete\s+(?:the\s+)?pet(?:\s+(?:number\s+)?(\d+))?")
_CHART = re.compile(r"(?i)chart|analyse the attached csv|analyze the attached csv|revenue by month")
_ASK = re.compile(r"(?i)\bask me\b")
_TOOL = re.compile(r"^/tool\s+(\S+)(?:\s+(\{.*\}))?\s*$", re.DOTALL)


async def maybe_tools(
    store: Any, run: dict[str, object], assistant: dict[str, object], text: str
) -> bool:
    """Execute a planned tool turn. Return false when the model should answer alone."""
    if _ASK.search(text):
        _ask(store, run, assistant)
        return True
    planned = _plan(store, run, text)
    if not planned:
        return False
    pipeline = ToolPipeline(store)
    previews: list[dict[str, object]] = []
    parts: list[str] = []
    for index, call in enumerate(planned):
        arguments = call["arguments"]
        version_id = call["tool_version_id"]
        digest = call_args_hash(str(version_id), arguments)
        model_call_id = f"call_{index}"
        store._emit(
            run,
            "tool_call.started",
            {
                "tool_call_id": model_call_id,
                "model_call_id": model_call_id,
                "qualified_name": call["qualified_name"],
                "title": call["title"],
                "risk_class": call["risk_class"],
                "arguments_preview": arguments,
            },
        )
        result = pipeline.execute(
            {
                "tenant_id": run.get("tenant_id"),
                "user_id": run.get("user_id"),
                "run_id": run.get("id"),
                "agent_id": run.get("agent_id"),
                "agent_version_id": run.get("agent_version_id"),
                "tool_version_id": version_id,
                "arguments": arguments,
                "args_hash": digest,
                "model_call_id": model_call_id,
            }
        )
        if result.get("status") == "awaiting_approval":
            _pause(store, run, assistant, call, result, arguments)
            return True
        event = "tool_call.completed" if result.get("status") == "succeeded" else "tool_call.failed"
        error_body = result.get("error")
        connect_url = error_body.get("connect_url") if isinstance(error_body, dict) else None
        store._emit(
            run,
            event,
            {
                "tool_call_id": result.get("tool_call_id") or model_call_id,
                "status": result.get("status"),
                "result_preview": result.get("result_preview"),
                "error": error_body,
                "connect_url": connect_url,
                "latency_ms": result.get("latency_ms"),
            },
        )
        previews.append(
            {
                "qualified_name": call["qualified_name"],
                "status": result.get("status"),
                "arguments": result.get("arguments_redacted") or arguments,
                "result_preview": result.get("result_preview"),
                "error": result.get("error"),
            }
        )
        parts.append(str(result.get("result_preview") or ""))
    answer = _answer(text, parts)
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
    store._emit(run, "message.completed", {"message_id": str(assistant_id), "text": answer})
    store._emit(
        run,
        "run.completed",
        {"final_message_id": str(assistant_id), "usage": {"tokens_in": 1, "tokens_out": 1}},
    )
    return True


def _plan(store: Any, run: dict[str, object], text: str) -> list[dict[str, Any]]:  # noqa: PLR0911
    version_id = run.get("agent_version_id")
    if not isinstance(version_id, uuid.UUID):
        return []
    version = store.versions.get(version_id)
    definition = version.get("definition") if isinstance(version, dict) else None
    if not isinstance(definition, dict):
        return []
    budget = definition.get("budget")
    if isinstance(budget, dict) and int(budget.get("max_tool_calls") or 0) <= 0:
        return []
    servers = {
        str(item.get("server"))
        for item in definition.get("tools", [])
        if isinstance(item, dict) and isinstance(item.get("server"), str)
    }
    command = _TOOL.match(text.strip())
    if command:
        return _by_name(store, command.group(1), command.group(2) or "{}")
    ticket = _TICKET.search(text)
    if ticket and "tickets" in servers:
        return _by_name(store, "tickets.create_ticket", "", title=ticket.group(1).strip())
    if _ORDERS.search(text) and "warehouse" in servers:
        return _by_name(store, "warehouse.run_query", "", sql="SELECT count(*) FROM public.orders")
    pet = _PET.search(text)
    if pet and "petstore" in servers:
        name = pet.group(1).strip().rstrip(".")
        return _by_name(store, "petstore.create_pet", "", body={"body": {"name": name}})
    deleted = _DELETE.search(text)
    if deleted and "petstore" in servers:
        return _by_name(store, "petstore.delete_pet", "", pet_id=int(deleted.group(1) or "1"))
    if _CHART.search(text) and "sandbox" in servers:
        from ar_domain.sandboxes.runtime import chart_command  # noqa: PLC0415

        return _by_name(store, "sandbox.exec", "", command=chart_command())
    return []


def _by_name(
    store: Any,
    qualified: str,
    raw_json: str,
    *,
    title: str = "",
    sql: str = "",
    body: dict[str, object] | None = None,
    pet_id: int | None = None,
    command: str = "",
) -> list[dict[str, Any]]:
    import orjson  # noqa: PLC0415

    arguments: dict[str, object] = {}
    if body is not None:
        arguments = body
    elif pet_id is not None:
        arguments = {"petId": pet_id}
    elif title:
        arguments = {"title": title}
    elif command:
        arguments = {"command": command, "cwd": "/workspace", "timeout_s": 60}
    elif sql:
        arguments = {"sql": sql}
    elif raw_json.strip():
        parsed = orjson.loads(raw_json)
        if isinstance(parsed, dict):
            arguments = parsed
    for row in store.tool_versions.values():
        if row.get("qualified_name") != qualified:
            continue
        server_version = store.tool_server_versions.get(row.get("tool_server_version_id"))
        server = None
        if isinstance(server_version, dict):
            server = store.tool_servers.get(server_version.get("tool_server_id"))
        if not isinstance(server, dict) or server.get("current_version_id") != row.get(
            "tool_server_version_id"
        ):
            continue
        return [
            {
                "tool_version_id": row["id"],
                "qualified_name": qualified,
                "title": row.get("title") or qualified,
                "risk_class": row.get("risk_class"),
                "arguments": arguments,
            }
        ]
    return []


def _policy_hash(result: dict[str, object]) -> object:
    policy = result.get("policy")
    if isinstance(policy, dict):
        return policy.get("args_hash")
    return None


def _pause(  # noqa: PLR0917
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    call: dict[str, Any],
    result: dict[str, object],
    arguments: dict[str, object],
) -> None:
    run["status"] = "waiting_approval"
    run["pending_approval"] = {
        "approval_id": uuid.UUID(str(result.get("approval_id"))),
        "tool_version_id": call["tool_version_id"],
        "arguments": arguments,
        "args_hash": _policy_hash(result)
        or call_args_hash(str(call["tool_version_id"]), arguments),
        "model_call_id": result.get("tool_call_id"),
    }
    # The hash the pipeline stored is the one on the approval, not the model id.
    approval = result.get("approval")
    if isinstance(approval, dict) and approval.get("id"):
        row = store.approvals.get(uuid.UUID(str(approval["id"])))
        if isinstance(row, dict):
            pending = run["pending_approval"]
            if isinstance(pending, dict):
                pending["args_hash"] = row.get("args_hash")
                pending["model_call_id"] = row.get("tool_call_id")
                pending["tool_call_id"] = row.get("tool_call_id")
    text = "Waiting for approval before this tool runs."
    assistant["text"] = text
    assistant["content"] = [{"type": "text", "text": text}]
    assistant["status"] = "waiting_approval"
    assistant["tool_calls"] = [
        {
            "qualified_name": call["qualified_name"],
            "status": "awaiting_approval",
            "arguments": arguments,
            "result_preview": text,
            "approval_id": str(result.get("approval_id") or ""),
        }
    ]
    store._emit(
        run,
        "tool_call.approval_required",
        {
            "tool_call_id": str(result.get("tool_call_id") or ""),
            "approval_id": str(result.get("approval_id") or ""),
            "qualified_name": call["qualified_name"],
            "risk_class": call["risk_class"],
        },
    )
    store._emit(run, "run.status", {"status": "waiting_approval"})


def _ask(store: Any, run: dict[str, object], assistant: dict[str, object]) -> None:
    prompt = "What should I use?"
    run["status"] = "waiting_input"
    assistant["text"] = prompt
    assistant["content"] = [{"type": "text", "text": prompt}]
    assistant["status"] = "waiting_input"
    store._emit(run, "input.required", {"prompt": prompt})
    store._emit(run, "run.status", {"status": "waiting_input"})


def _answer(text: str, parts: list[str]) -> str:
    body = " ".join(part for part in parts if part)
    if not body:
        return "I could not run that tool."
    if text.lower().startswith("/tool"):
        return body
    return body
