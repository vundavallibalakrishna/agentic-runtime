"""A2A agent card, tasks, push webhooks and a client tool."""

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
    "tasks/list",
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
        "capabilities": {"streaming": True, "push_notifications": True},
        "default_input_modes": ["text/plain"],
        "default_output_modes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": slug,
                "name": str(agent.get("name") or slug),
                "description": description,
                "tags": ["agent"],
            },
            {
                "id": "research",
                "name": "Research",
                "description": "Search, read and cite sources for a question.",
                "tags": ["research"],
            },
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
        "events": [
            {"id": "1", "kind": "status", "state": state},
            *([{"id": "2", "kind": "artifact", "text": output}] if output else []),
        ],
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
    raw_meta = message.get("metadata")
    metadata = raw_meta if isinstance(raw_meta, dict) else {}
    research = str(metadata.get("mode") or params.get("mode") or "") == "research"
    context = message.get("context_id") or message.get("contextId") or params.get("context_id")
    if context:
        conversation_id = uuid.UUID(str(context))
        _conversation_for(store, key, conversation_id)
    else:
        created = create_conversation(store, key, slug)
        conversation_id = uuid.UUID(str(created["id"]))
    reply, _replayed = await send_message(
        store, key, slug, conversation_id, text, [], "", research=research
    )
    state = _state_for(reply)
    output = str(reply.get("output") or "")
    if state == "input-required":
        output = "Approval required"
    run_id = uuid.UUID(str(reply["id"])) if reply.get("id") else None
    row = _task_row(store, key, agent, conversation_id, run_id, state, output)
    parts = reply.get("content")
    if isinstance(parts, list):
        extra = [
            part
            for part in parts
            if isinstance(part, dict) and part.get("type") not in {"text", "reasoning"}
        ]
        if extra:
            artifacts = row.get("artifacts")
            if isinstance(artifacts, list):
                artifacts.append(
                    {
                        "artifact_id": str(new_id()),
                        "name": "content",
                        "parts": extra,
                    }
                )
    embedded = _embedded_push(params)
    if embedded is not None:
        with contextlib.suppress(ArError):
            set_push_config(store, key, row["id"], embedded)
    audit_key(
        store,
        tenant_id=key["tenant_id"],
        actor_id=_user_id(key),
        action="a2a_task.created",
        key_id=key["id"],
        label=str(key.get("label") or ""),
        extra={"task_id": str(row["id"]), "state": state, "agent_id": str(agent["id"])},
    )
    deliver_push(store, key, row)
    return task_body(row)


def resubscribe(store: Any, key: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Return the task and the events after the caller's cursor."""
    task_id = _task_param(params)
    body = get_task(store, key, task_id)
    row = _book(store, "a2a_tasks").get(task_id)
    events = row.get("events") if isinstance(row, dict) else []
    if not isinstance(events, list):
        events = []
    cursor = str(params.get("last_event_id") or params.get("lastEventId") or "")
    if cursor:
        events = [event for event in events if str(event.get("id")) > cursor]
    body["events"] = events
    body["resubscribed"] = True
    return body


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
    deliver_push(store, key, row)
    return task_body(row)


def list_tasks(store: Any, key: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """One page of tasks this key created. The page token is the last task id."""
    size = _page_size(params.get("pageSize") if "pageSize" in params else params.get("page_size"))
    rows = [
        row
        for row in _book(store, "a2a_tasks").values()
        if isinstance(row, dict) and row.get("key_id") == key.get("id")
    ]
    context = params.get("contextId") or params.get("context_id")
    if context:
        rows = [row for row in rows if str(row.get("conversation_id")) == str(context)]
    status = params.get("status")
    if status:
        rows = [row for row in rows if str(row.get("state")) == str(status)]
    rows.sort(key=lambda item: (str(item.get("created_at")), str(item.get("id"))), reverse=True)
    token = str(params.get("pageToken") or params.get("page_token") or "")
    if token:
        index = next((pos for pos, row in enumerate(rows) if str(row.get("id")) == token), None)
        if index is None:
            raise ArError(ErrorCode.VALIDATION_FAILED, "page token was not found")
        rows = rows[index + 1 :]
    page = rows[:size]
    next_token = str(page[-1]["id"]) if len(rows) > size and page else ""
    return {"tasks": [task_body(row) for row in page], "next_page_token": next_token}


def set_push_config(
    store: Any, key: dict[str, Any], task_id: uuid.UUID, config: dict[str, Any]
) -> dict[str, Any]:
    row = _owned_task(store, key, task_id)
    url = str(config.get("url") or "").strip()
    if not url:
        raise ArError(ErrorCode.VALIDATION_FAILED, "a push url is required")
    problem = guard_public(url, allow=["*"], loopback=True)
    if problem:
        raise ArError(ErrorCode.VALIDATION_FAILED, problem)
    token = str(config.get("token") or "")
    if len(token) > 256:
        raise ArError(ErrorCode.VALIDATION_FAILED, "push token is too long")
    config_id = str(config.get("id") or config.get("config_id") or "default").strip() or "default"
    if len(config_id) > 64:
        raise ArError(ErrorCode.VALIDATION_FAILED, "push config id is too long")
    book = _book(store, "a2a_push_configs")
    current = _push_row(book, task_id, config_id)
    now = utcnow()
    if current is None:
        item_id = new_id()
        current = {
            "id": item_id,
            "tenant_id": key["tenant_id"],
            "task_id": task_id,
            "key_id": key["id"],
            "config_id": config_id,
            "url": url,
            "token": token,
            "created_at": now,
            "updated_at": now,
        }
        book[item_id] = current
    else:
        current["url"] = url
        current["token"] = token
        current["updated_at"] = now
    audit_key(
        store,
        tenant_id=key["tenant_id"],
        actor_id=_user_id(key),
        action="a2a_push.configured",
        key_id=key["id"],
        label=str(key.get("label") or ""),
        extra={"task_id": str(task_id), "config_id": config_id},
    )
    return _push_body(current, row)


def get_push_config(store: Any, key: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    task_id = _task_param(params)
    _owned_task(store, key, task_id)
    config_id = str(params.get("id") or params.get("config_id") or params.get("configId") or "")
    found = _push_for_task(store, task_id, key, config_id or None)
    if not found:
        raise NotFoundError("push config not found")
    chosen = found[0]
    if config_id:
        match = next((row for row in found if str(row.get("config_id")) == config_id), None)
        if match is None:
            raise NotFoundError("push config not found")
        chosen = match
    return _push_body(chosen, _owned_task(store, key, task_id))


def delete_push_config(store: Any, key: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    task_id = _task_param(params)
    task = _owned_task(store, key, task_id)
    config_id = str(
        params.get("id") or params.get("config_id") or params.get("configId") or "default"
    )
    book = _book(store, "a2a_push_configs")
    target = next(
        (
            row
            for row in book.values()
            if isinstance(row, dict)
            and row.get("task_id") == task_id
            and row.get("key_id") == key.get("id")
            and str(row.get("config_id")) == config_id
        ),
        None,
    )
    if not isinstance(target, dict):
        raise NotFoundError("push config not found")
    book.pop(target["id"], None)
    audit_key(
        store,
        tenant_id=key["tenant_id"],
        actor_id=_user_id(key),
        action="a2a_push.removed",
        key_id=key["id"],
        label=str(key.get("label") or ""),
        extra={"task_id": str(task_id), "config_id": config_id},
    )
    return _push_body(target, task)


def list_push_configs(store: Any, key: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    task_id = _task_param(params)
    task = _owned_task(store, key, task_id)
    rows = _push_for_task(store, task_id, key, None)
    return {"configs": [_push_body(row, task) for row in rows]}


def deliver_push(store: Any, key: dict[str, Any], task: dict[str, Any]) -> None:
    """POST the task to each saved webhook. A failed call does not fail the task."""
    task_id = task.get("id")
    if not isinstance(task_id, uuid.UUID):
        return
    for config in _push_for_task(store, task_id, key, None):
        url = str(config.get("url") or "")
        if guard_public(url, allow=["*"], loopback=True):
            continue
        headers = {"accept": "application/json", "content-type": "application/json"}
        token = str(config.get("token") or "")
        if token:
            headers["authorization"] = f"Bearer {token}"
        try:
            fetch_text(store, "POST", url, headers=headers, json_body=task_body(task), timeout=10)
        except httpx.HTTPError, ArError, OSError:
            continue


def _push_method(
    store: Any, key: dict[str, Any], method: str, params: dict[str, Any]
) -> dict[str, Any]:
    if method == "tasks/pushNotificationConfig/list":
        return list_push_configs(store, key, params)
    if method == "tasks/pushNotificationConfig/get":
        return get_push_config(store, key, params)
    if method == "tasks/pushNotificationConfig/delete":
        return delete_push_config(store, key, params)
    nested = params.get("pushNotificationConfig") or params.get("push_notification_config")
    config = nested if isinstance(nested, dict) else {}
    if not config and params.get("url"):
        config = params
    return set_push_config(store, key, _task_param(params), config)


def _embedded_push(params: dict[str, Any]) -> dict[str, Any] | None:
    configuration = params.get("configuration")
    if not isinstance(configuration, dict):
        return None
    raw = configuration.get("pushNotificationConfig") or configuration.get(
        "push_notification_config"
    )
    return raw if isinstance(raw, dict) and raw.get("url") else None


def _owned_task(store: Any, key: dict[str, Any], task_id: uuid.UUID) -> dict[str, Any]:
    row = _book(store, "a2a_tasks").get(task_id)
    if not isinstance(row, dict) or row.get("key_id") != key.get("id"):
        raise NotFoundError("task not found")
    return row


def _task_param(params: dict[str, Any]) -> uuid.UUID:
    raw = params.get("taskId") or params.get("task_id") or params.get("id")
    if not raw:
        raise ArError(ErrorCode.VALIDATION_FAILED, "a task id is required")
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise ArError(ErrorCode.VALIDATION_FAILED, "task id is not a uuid") from exc


def _page_size(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 20
    if isinstance(value, int):
        size = value
    elif isinstance(value, str) and value.isdigit():
        size = int(value)
    else:
        return 20
    return min(max(size, 1), 100)


def _push_for_task(
    store: Any, task_id: uuid.UUID, key: dict[str, Any], config_id: str | None
) -> list[dict[str, Any]]:
    book = _book(store, "a2a_push_configs")
    rows = [
        row
        for row in book.values()
        if isinstance(row, dict)
        and row.get("task_id") == task_id
        and row.get("key_id") == key.get("id")
    ]
    if config_id:
        rows = [row for row in rows if str(row.get("config_id")) == config_id]
    rows.sort(key=lambda item: str(item.get("config_id")))
    return rows


def _push_row(book: dict[Any, Any], task_id: uuid.UUID, config_id: str) -> dict[str, Any] | None:
    for row in book.values():
        if (
            isinstance(row, dict)
            and row.get("task_id") == task_id
            and str(row.get("config_id")) == config_id
        ):
            return row
    return None


def _push_body(config: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": str(task.get("id") or config.get("task_id")),
        "push_notification_config": {
            "id": str(config.get("config_id") or "default"),
            "url": str(config.get("url") or ""),
            "token": str(config.get("token") or ""),
        },
    }


async def rpc(
    store: Any, key: dict[str, Any], slug: str, message: dict[str, Any]
) -> dict[str, Any]:
    method = str(message.get("method") or "")
    request_id = message.get("id")
    raw_params = message.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
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
    if method == "tasks/list":
        return list_tasks(store, key, params)
    if method.startswith("tasks/pushNotificationConfig/"):
        return _push_method(store, key, method, params)
    if method == "tasks/resubscribe":
        return resubscribe(store, key, params)
    task_raw = params.get("id") or params.get("task_id") or params.get("taskId")
    try:
        task_id = uuid.UUID(str(task_raw))
    except ValueError as exc:
        raise ArError(ErrorCode.VALIDATION_FAILED, "a task id is required") from exc
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
