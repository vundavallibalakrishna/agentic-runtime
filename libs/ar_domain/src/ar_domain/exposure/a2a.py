"""A2A agent card, tasks, and a client tool. Push notifications and gRPC are not implemented."""

from __future__ import annotations

import contextlib
import uuid
from typing import TYPE_CHECKING

import httpx
import orjson

from ar_common.errors import ArError, ErrorCode, NotFoundError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.exposure.keys import _book, audit_key
from ar_domain.exposure.runs import (
    _conversation_for,
    _user_id,
    agent_for_key,
    create_conversation,
    definition_of,
    send_message,
)
from ar_domain.tools.http_tools import fetch_text, guard_public
from ar_domain.tools.named_secrets import read_named_secret

if TYPE_CHECKING:
    from typing import Any

_IMPLEMENTED = {
    "message/send",
    "tasks/send",
    "message/stream",
    "tasks/sendSubscribe",
    "tasks/get",
    "tasks/cancel",
}
_NOT_IMPLEMENTED = {
    "tasks/pushNotificationConfig/set",
    "tasks/pushNotificationConfig/get",
    "tasks/pushNotificationConfig/delete",
    "tasks/pushNotificationConfig/list",
    "tasks/resubscribe",
}


def agent_card(store: Any, key: dict[str, Any], slug: str, base_url: str) -> dict[str, Any]:
    """The card a client fetches before it sends a task. The key selects the agent."""
    agent = agent_for_key(store, key, slug)
    definition = definition_of(store, agent)
    raw_contract = definition.get("contract")
    contract = raw_contract if isinstance(raw_contract, dict) else {}
    description = str(contract.get("description") or agent.get("description") or agent.get("name"))
    root = base_url.rstrip("/")
    return {
        "name": str(agent.get("name") or slug),
        "description": description,
        "url": f"{root}/v1/agents/{slug}/a2a",
        "version": "1",
        "protocol_version": "0.3.0",
        "capabilities": {"streaming": True, "push_notifications": False},
        "default_input_modes": ["text/plain"],
        "default_output_modes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": slug,
                "name": str(agent.get("name") or slug),
                "description": description,
                "tags": ["agent"],
            }
        ],
        "security_schemes": {"bearer": {"type": "http", "scheme": "bearer"}},
        "security": [{"bearer": []}],
    }


def _text_parts(message: dict[str, Any]) -> str:
    parts = message.get("parts")
    if isinstance(parts, list):
        chunks = [
            str(part.get("text") or "")
            for part in parts
            if isinstance(part, dict)
            and str(part.get("kind") or part.get("type") or "") in {"text", "text/plain"}
        ]
        if chunks:
            return "\n".join(chunks).strip()
    return str(message.get("text") or "").strip()


def _task_row(  # noqa: PLR0917
    store: Any,
    key: dict[str, Any],
    agent: dict[str, Any],
    conversation_id: uuid.UUID,
    run_id: uuid.UUID | None,
    state: str,
    output: str,
) -> dict[str, Any]:
    task_id = new_id()
    artifacts = []
    if output:
        artifacts.append(
            {
                "artifact_id": str(new_id()),
                "name": "reply",
                "parts": [{"kind": "text", "text": output}],
            }
        )
    row = {
        "id": task_id,
        "tenant_id": key["tenant_id"],
        "agent_id": agent["id"],
        "key_id": key["id"],
        "conversation_id": conversation_id,
        "run_id": run_id,
        "state": state,
        "output_text": output,
        "artifacts": artifacts,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    _book(store, "a2a_tasks")[task_id] = row
    return row


def task_body(row: dict[str, Any]) -> dict[str, Any]:
    output = str(row.get("output_text") or "")
    message = {
        "role": "agent",
        "message_id": str(row.get("id")),
        "parts": [{"kind": "text", "text": output}],
    }
    return {
        "id": str(row.get("id")),
        "context_id": str(row.get("conversation_id")),
        "status": {"state": str(row.get("state") or "completed"), "message": message},
        "artifacts": row.get("artifacts") if isinstance(row.get("artifacts"), list) else [],
    }


def _state_for(reply: dict[str, Any]) -> str:
    finish = str(reply.get("finish_reason") or "")
    if finish == "approval_required":
        return "input-required"
    if finish in {"failed", "cancelled"}:
        return "failed" if finish == "failed" else "canceled"
    return "completed"


async def send_task(
    store: Any,
    key: dict[str, Any],
    slug: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    agent = agent_for_key(store, key, slug)
    raw_message = params.get("message")
    message = raw_message if isinstance(raw_message, dict) else {}
    text = _text_parts(message)
    if not text:
        raise ArError(ErrorCode.VALIDATION_FAILED, "a text part is required")
    context = message.get("context_id") or message.get("contextId") or params.get("context_id")
    if context:
        conversation_id = uuid.UUID(str(context))
        _conversation_for(store, key, conversation_id)
    else:
        created = create_conversation(store, key, slug)
        conversation_id = uuid.UUID(str(created["id"]))
    reply, _replayed = await send_message(store, key, slug, conversation_id, text, [], "")
    state = _state_for(reply)
    output = str(reply.get("output") or "")
    if state == "input-required":
        output = "Approval required"
    run_id = uuid.UUID(str(reply["id"])) if reply.get("id") else None
    row = _task_row(store, key, agent, conversation_id, run_id, state, output)
    audit_key(
        store,
        tenant_id=key["tenant_id"],
        actor_id=_user_id(key),
        action="a2a_task.created",
        key_id=key["id"],
        label=str(key.get("label") or ""),
        extra={"task_id": str(row["id"]), "state": state, "agent_id": str(agent["id"])},
    )
    return task_body(row)


def get_task(store: Any, key: dict[str, Any], task_id: uuid.UUID) -> dict[str, Any]:
    row = _book(store, "a2a_tasks").get(task_id)
    if not isinstance(row, dict) or row.get("key_id") != key.get("id"):
        raise NotFoundError("task not found")
    return task_body(row)


def cancel_task(store: Any, key: dict[str, Any], slug: str, task_id: uuid.UUID) -> dict[str, Any]:
    row = _book(store, "a2a_tasks").get(task_id)
    if not isinstance(row, dict) or row.get("key_id") != key.get("id"):
        raise NotFoundError("task not found")
    agent_for_key(store, key, slug)
    run_id = row.get("run_id")
    if isinstance(run_id, uuid.UUID):
        run = store.runs.get(run_id)
        if isinstance(run, dict) and str(run.get("status") or "") in {
            "queued",
            "running",
            "waiting_approval",
            "waiting_input",
        }:
            with contextlib.suppress(ArError):
                store.cancel_run(key["tenant_id"], _user_id(key), run_id)
    if row.get("state") not in {"completed", "failed", "canceled"}:
        row["state"] = "canceled"
        row["updated_at"] = utcnow()
    audit_key(
        store,
        tenant_id=key["tenant_id"],
        actor_id=_user_id(key),
        action="a2a_task.cancelled",
        key_id=key["id"],
        label=str(key.get("label") or ""),
        extra={"task_id": str(task_id)},
    )
    return task_body(row)


async def rpc(
    store: Any, key: dict[str, Any], slug: str, message: dict[str, Any]
) -> dict[str, Any]:
    method = str(message.get("method") or "")
    request_id = message.get("id")
    raw_params = message.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    if method in _NOT_IMPLEMENTED:
        return _error(request_id, -32601, f"Method not implemented: {method}")
    if method not in _IMPLEMENTED:
        return _error(request_id, -32601, f"Method not found: {method}")
    try:
        result = await _call(store, key, slug, method, params)
    except ArError as exc:
        return _error(request_id, -32000, exc.detail)
    except NotFoundError:
        return _error(request_id, -32001, "not found")
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


async def _call(
    store: Any, key: dict[str, Any], slug: str, method: str, params: dict[str, Any]
) -> dict[str, Any]:
    if method in {"message/send", "tasks/send", "message/stream", "tasks/sendSubscribe"}:
        return await send_task(store, key, slug, params)
    task_raw = params.get("id") or params.get("task_id") or params.get("taskId")
    task_id = uuid.UUID(str(task_raw))
    if method == "tasks/get":
        return get_task(store, key, task_id)
    return cancel_task(store, key, slug, task_id)


def _error(request_id: object, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def call_remote(store: Any, arguments: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR0911
    """Call another agent's public A2A endpoint. The bearer token comes from a named secret."""
    url = str(arguments.get("url") or "").strip()
    message = str(arguments.get("message") or "").strip()
    if not url or not message:
        return _tool_error("validation_failed", "url and message are required")
    problem = guard_public(url, allow=["*"], loopback=True)
    if problem:
        return _tool_error("egress_denied", problem)
    secret_name = str(arguments.get("secret_name") or arguments.get("secretName") or "")
    token = ""
    if secret_name:
        token = read_named_secret(store, arguments.get("_tenant_id"), secret_name) or ""
        if not token:
            return _tool_error("credential_required", "named secret was not found")
    headers = {"accept": "application/json", "content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    try:
        endpoint, card_error = _endpoint(store, url, headers)
    except httpx.HTTPError:
        return _tool_error("upstream_error", "remote agent card did not respond")
    if card_error:
        return card_error
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": message}]}},
    }
    try:
        status, raw = fetch_text(
            store, "POST", endpoint, headers=headers, json_body=payload, timeout=90
        )
    except httpx.HTTPError:
        return _tool_error("upstream_error", "remote agent did not respond")
    if status >= 300:
        return _tool_error("upstream_error", f"remote agent returned {status}")
    return _remote_text(raw)


def _endpoint(store: Any, url: str, headers: dict[str, str]) -> tuple[str, dict[str, Any] | None]:
    if not url.endswith("agent-card.json"):
        return url, None
    status, raw = fetch_text(store, "GET", url, headers=headers, timeout=20)
    if status >= 300:
        return "", _tool_error("upstream_error", f"agent card returned {status}")
    try:
        card = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return "", _tool_error("upstream_error", "agent card was not json")
    target = str(card.get("url") or "") if isinstance(card, dict) else ""
    if not target:
        return "", _tool_error("upstream_error", "agent card has no url")
    problem = guard_public(target, allow=["*"], loopback=True)
    if problem:
        return "", _tool_error("egress_denied", problem)
    return target, None


def _remote_text(raw: str) -> dict[str, Any]:
    try:
        body = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return _tool_error("upstream_error", "remote agent did not return json")
    if not isinstance(body, dict):
        return _tool_error("upstream_error", "remote agent did not return json")
    result = body.get("result") if isinstance(body.get("result"), dict) else body
    text = _artifact_text(result if isinstance(result, dict) else {})
    state = ""
    status = result.get("status") if isinstance(result, dict) else None
    if isinstance(status, dict):
        state = str(status.get("state") or "")
    if state == "input-required":
        text = text or "Approval required"
    return {
        "text": text or "The remote agent returned no text.",
        "structured": {"state": state or "completed"},
        "is_error": False,
    }


def _artifact_text(result: dict[str, Any]) -> str:
    artifacts = result.get("artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            found = _text_parts(artifact)
            if found:
                return found
    status = result.get("status")
    if isinstance(status, dict) and isinstance(status.get("message"), dict):
        return _text_parts(status["message"])
    return ""


def _tool_error(code: str, text: str) -> dict[str, Any]:
    return {"text": text, "structured": {}, "is_error": True, "code": code}


def stream_events(task: dict[str, Any]) -> list[dict[str, Any]]:
    """SSE payloads for message/stream. The task is already finished."""
    return [{"kind": "task", "task": task}]
