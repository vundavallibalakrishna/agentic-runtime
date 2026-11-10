"""Run a published agent for an external key. Callers never use the internal chat route."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import orjson

from ar_common.errors import ArError, ConflictError, ErrorCode, NotFoundError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.events.idempotency import StoredResponse
from ar_domain.exposure.keys import (
    _book,
    audit_key,
    request_fingerprint,
    take_quota,
)
from ar_domain.tools.logic import as_mapping

if TYPE_CHECKING:
    from typing import Any

_PUBLISHED = {"published", "active"}


def published_agent(store: Any, tenant_id: uuid.UUID, slug: str) -> dict[str, Any]:
    for agent in store.agents.values():
        if not isinstance(agent, dict):
            continue
        if agent.get("tenant_id") == tenant_id and agent.get("slug") == slug:
            return _runnable(agent)
    raise NotFoundError("agent not found")


def _runnable(agent: dict[str, Any]) -> dict[str, Any]:
    if agent.get("disabled"):
        raise ArError(ErrorCode.RESOURCE_DISABLED, "agent is disabled")
    published = agent.get("published_version_id") is not None
    if str(agent.get("status") or "") not in _PUBLISHED or not published:
        raise NotFoundError("agent is not published")
    return agent


def agent_for_key(store: Any, key: dict[str, Any], slug: str) -> dict[str, Any]:
    """Agent-scoped keys only reach their own agent. A workspace key reaches published agents."""
    tenant_id = key.get("tenant_id")
    if not isinstance(tenant_id, uuid.UUID):
        raise NotFoundError("agent not found")
    agent = published_agent(store, tenant_id, slug)
    if str(key.get("scope") or "agent") == "workspace":
        return agent
    if agent.get("id") != key.get("agent_id"):
        raise NotFoundError("agent not found")
    return agent


def definition_of(store: Any, agent: dict[str, Any]) -> dict[str, Any]:
    version_id = agent.get("published_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    return definition if isinstance(definition, dict) else {}


def _user_id(key: dict[str, Any]) -> uuid.UUID:
    user_id = key.get("created_by_user_id")
    if isinstance(user_id, uuid.UUID):
        return user_id
    raise NotFoundError("agent not found")


def _grant(
    store: Any,
    key: dict[str, Any],
    agent: dict[str, Any],
    conversation_id: uuid.UUID,
    run_id: uuid.UUID | None,
) -> None:
    grant_id = new_id()
    _book(store, "agent_api_grants")[grant_id] = {
        "id": grant_id,
        "tenant_id": key["tenant_id"],
        "key_id": key["id"],
        "agent_id": agent["id"],
        "conversation_id": conversation_id,
        "run_id": run_id,
        "created_at": utcnow(),
    }


def _grants_for(store: Any, key: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in _book(store, "agent_api_grants").values()
        if isinstance(row, dict) and row.get("key_id") == key.get("id")
    ]


def create_conversation(store: Any, key: dict[str, Any], slug: str) -> dict[str, Any]:
    agent = agent_for_key(store, key, slug)
    created = store.create_conversation(key["tenant_id"], _user_id(key), agent["id"])
    conversation_id = uuid.UUID(str(created["id"]))
    _grant(store, key, agent, conversation_id, None)
    audit_key(
        store,
        tenant_id=key["tenant_id"],
        actor_id=_user_id(key),
        action="agent_api_call.accepted",
        key_id=key["id"],
        label=str(key.get("label") or ""),
        extra={"path": "conversations", "agent_id": str(agent["id"])},
    )
    return {"id": str(conversation_id), "agent_id": str(agent["id"]), "slug": slug}


def _conversation_for(store: Any, key: dict[str, Any], conversation_id: uuid.UUID) -> None:
    if any(row.get("conversation_id") == conversation_id for row in _grants_for(store, key)):
        return
    raise NotFoundError("conversation not found")


def upload_file(  # noqa: PLR0917
    store: Any, key: dict[str, Any], slug: str, name: str, mime: str, data: bytes
) -> dict[str, Any]:
    agent_for_key(store, key, slug)
    uploaded = store.upload(key["tenant_id"], _user_id(key), name, mime, data)
    audit_key(
        store,
        tenant_id=key["tenant_id"],
        actor_id=_user_id(key),
        action="agent_api_call.accepted",
        key_id=key["id"],
        label=str(key.get("label") or ""),
        extra={"path": "files", "file_id": str(uploaded.get("id"))},
    )
    return {"id": str(uploaded.get("id")), "name": name, "mime_type": mime}


def _reply(store: Any, run_id: uuid.UUID) -> dict[str, Any]:
    run = store.runs.get(run_id)
    if not isinstance(run, dict):
        raise NotFoundError("run not found")
    status = str(run.get("status") or "")
    messages = store.messages
    assistant_id = run.get("assistant_message_id")
    text = ""
    if isinstance(assistant_id, uuid.UUID):
        message = messages.get(assistant_id)
        if isinstance(message, dict):
            text = str(message.get("text") or "")
    approval_id = None
    finish = "stop"
    if status == "waiting_approval":
        finish = "approval_required"
        pending = run.get("pending_approval")
        if isinstance(pending, dict) and pending.get("approval_id") is not None:
            approval_id = str(pending.get("approval_id"))
        if not text:
            text = "Approval required"
    elif status in {"failed", "cancelled"}:
        finish = status
    raw_usage = run.get("usage")
    usage = raw_usage if isinstance(raw_usage, dict) else {}
    body = {
        "id": str(run_id),
        "conversation_id": str(run.get("conversation_id")),
        "status": "approval_required" if finish == "approval_required" else status,
        "output": text,
        "finish_reason": finish,
        "usage": {
            "tokens_in": int(usage.get("tokens_in") or 0),
            "tokens_out": int(usage.get("tokens_out") or 0),
            "tokensIn": int(usage.get("tokens_in") or 0),
            "tokensOut": int(usage.get("tokens_out") or 0),
            "cachedTokens": int(usage.get("cached_tokens") or 0),
            "modelCalls": int(usage.get("model_calls") or 0),
            "toolCalls": int(usage.get("tool_calls") or 0),
            "costMicros": int(usage.get("cost_micros") or 0),
            "sandboxCpuSeconds": int(usage.get("sandbox_cpu_seconds") or 0),
            "elapsedMs": int(usage.get("elapsed_ms") or 0),
            "cost_micros": int(usage.get("cost_micros") or 0),
            "model_calls": int(usage.get("model_calls") or 0),
            "tool_calls": int(usage.get("tool_calls") or 0),
        },
    }
    if approval_id:
        body["approval_id"] = approval_id
    return body


async def _replay(
    store: Any, key: dict[str, Any], header: str, fingerprint: str
) -> dict[str, Any] | None:
    """The stored reply for this key, from the shared store or the process book."""
    shared = await _shared_get(store, key, header)
    if shared is not None:
        if shared.request_hash != fingerprint:
            raise ArError(
                ErrorCode.IDEMPOTENCY_KEY_REUSED,
                "Idempotency-Key was reused with a different body",
            )
        if shared.status_code is None or not shared.body:
            raise ConflictError("a request with this Idempotency-Key is in flight")
        loaded = orjson.loads(shared.body)
        if isinstance(loaded, dict):
            return loaded
    if not header:
        return None
    existing = _idempotency_row(store, key["id"], header)
    if existing is None:
        return None
    if existing.get("request_hash") != fingerprint:
        raise ArError(
            ErrorCode.IDEMPOTENCY_KEY_REUSED,
            "Idempotency-Key was reused with a different body",
        )
    if existing.get("state") == "in_flight":
        raise ConflictError("a request with this Idempotency-Key is in flight")
    stored = existing.get("response")
    return stored if isinstance(stored, dict) and stored else None


async def _shared_get(store: Any, key: dict[str, Any], header: str) -> StoredResponse | None:
    shared = getattr(store, "shared_idempotency", None)
    if shared is None or not header:
        return None
    found = await shared.get((str(key["tenant_id"]), str(key["id"]), header))
    return found if isinstance(found, StoredResponse) else None


async def _shared_put(
    store: Any,
    key: dict[str, Any],
    header: str,
    fingerprint: str,
    body: dict[str, Any] | None,
    *,
    done: bool,
) -> None:
    shared = getattr(store, "shared_idempotency", None)
    if shared is None or not header:
        return
    await shared.put(
        (str(key["tenant_id"]), str(key["id"]), header),
        StoredResponse(
            request_hash=fingerprint,
            status_code=200 if done else None,
            body=None if body is None else orjson.dumps(body),
        ),
    )


def _idempotency_row(store: Any, key_id: uuid.UUID, header: str) -> dict[str, Any] | None:
    for row in _book(store, "agent_api_idempotency").values():
        if (
            isinstance(row, dict)
            and row.get("key_id") == key_id
            and row.get("idempotency_key") == header
        ):
            return row
    return None


def _remember_idempotency(  # noqa: PLR0917
    store: Any,
    key: dict[str, Any],
    header: str,
    fingerprint: str,
    response: dict[str, Any],
    run_id: uuid.UUID | None,
    *,
    state: str,
) -> None:
    existing = _idempotency_row(store, key["id"], header)
    if existing is None:
        item_id = new_id()
        _book(store, "agent_api_idempotency")[item_id] = {
            "id": item_id,
            "tenant_id": key["tenant_id"],
            "key_id": key["id"],
            "idempotency_key": header,
            "request_hash": fingerprint,
            "status_code": 200,
            "response": response,
            "run_id": run_id,
            "state": state,
            "created_at": utcnow(),
        }
        return
    existing["request_hash"] = fingerprint
    existing["response"] = response
    existing["run_id"] = run_id
    existing["state"] = state
    existing["status_code"] = 200


async def send_message(  # noqa: PLR0917
    store: Any,
    key: dict[str, Any],
    slug: str,
    conversation_id: uuid.UUID,
    text: str,
    attachment_ids: list[uuid.UUID],
    idempotency_key: str,
    *,
    research: bool = False,
) -> tuple[dict[str, Any], bool]:
    """Start at most one run for an idempotency key. A retry returns the stored reply."""
    run_id, replay = await begin_message(
        store,
        key,
        slug,
        conversation_id,
        text,
        attachment_ids,
        idempotency_key,
        research=research,
    )
    if replay is not None:
        return replay, True
    names = _attachment_names(store, attachment_ids)
    await store.generate(run_id, text, names)
    body = await finish_message(store, key, slug, idempotency_key, run_id, text, attachment_ids)
    return body, False


async def begin_message(  # noqa: PLR0917
    store: Any,
    key: dict[str, Any],
    slug: str,
    conversation_id: uuid.UUID,
    text: str,
    attachment_ids: list[uuid.UUID],
    idempotency_key: str,
    *,
    research: bool = False,
) -> tuple[uuid.UUID, dict[str, Any] | None]:
    """Open a run, or return the stored reply when the idempotency key already finished."""
    agent = agent_for_key(store, key, slug)
    _conversation_for(store, key, conversation_id)
    fingerprint = request_fingerprint(
        text, [str(item) for item in attachment_ids], str(conversation_id)
    )
    replay = await _replay(store, key, idempotency_key, fingerprint)
    if replay is not None:
        return uuid.UUID(str(replay["id"])), replay
    if not take_quota(key):
        audit_key(
            store,
            tenant_id=key["tenant_id"],
            actor_id=_user_id(key),
            action="agent_api_call.refused",
            key_id=key["id"],
            label=str(key.get("label") or ""),
            outcome="failure",
            extra={"reason": "quota"},
        )
        raise ArError(ErrorCode.QUOTA_EXCEEDED, "monthly quota exceeded")
    from ar_common.telemetry import record_run  # noqa: PLC0415
    from ar_domain.usage.service import UsageBook  # noqa: PLC0415

    UsageBook(store).assert_key(key["tenant_id"], key.get("id"))
    posted = store.post_message(
        key["tenant_id"],
        _user_id(key),
        conversation_id,
        text,
        attachment_ids=attachment_ids,
        schedule=False,
        research=research,
    )
    run = posted.get("run") if isinstance(posted, dict) else None
    run_id = uuid.UUID(str(run.get("id"))) if isinstance(run, dict) else None
    if isinstance(run, dict) and run_id is not None:
        stored = store.runs.get(run_id)
        if isinstance(stored, dict):
            stored["api_key_id"] = key.get("id")
            stored["trace_id"] = record_run(str(run_id))
    if run_id is None:
        raise NotFoundError("run not found")
    _grant(store, key, agent, conversation_id, run_id)
    if idempotency_key:
        _remember_idempotency(
            store, key, idempotency_key, fingerprint, {}, run_id, state="in_flight"
        )
        await _shared_put(store, key, idempotency_key, fingerprint, None, done=False)
    return run_id, None


async def finish_message(  # noqa: PLR0917
    store: Any,
    key: dict[str, Any],
    slug: str,
    idempotency_key: str,
    run_id: uuid.UUID,
    text: str,
    attachment_ids: list[uuid.UUID],
) -> dict[str, Any]:
    """Store the finished reply under the idempotency key."""
    agent = agent_for_key(store, key, slug)
    body = _reply(store, run_id)
    conversation_id = body.get("conversation_id")
    fingerprint = request_fingerprint(
        text, [str(item) for item in attachment_ids], str(conversation_id)
    )
    if idempotency_key:
        _remember_idempotency(
            store, key, idempotency_key, fingerprint, body, run_id, state="completed"
        )
        await _shared_put(store, key, idempotency_key, fingerprint, body, done=True)
    audit_key(
        store,
        tenant_id=key["tenant_id"],
        actor_id=_user_id(key),
        action="agent_api_call.accepted",
        key_id=key["id"],
        label=str(key.get("label") or ""),
        extra={"path": "messages", "run_id": str(run_id), "agent_id": str(agent["id"])},
    )
    return body


async def run_once(  # noqa: PLR0917
    store: Any,
    key: dict[str, Any],
    slug: str,
    text: str,
    attachment_ids: list[uuid.UUID],
    idempotency_key: str,
) -> tuple[dict[str, Any], bool]:
    """Create a fresh conversation and run one message — the stateless agent-run shape.

    Returns ``(reply, replayed)``; the reply carries the run id, output, finish reason and
    usage (tokens + cost). Idempotency is keyed on the key + Idempotency-Key + body only (not
    the conversation, which is minted per call), so a retry returns the same run rather than
    starting a second one; the same key with a different body is ``idempotency_key_reused``.
    """
    agent_for_key(store, key, slug)  # validate the agent is reachable by this key
    fingerprint = request_fingerprint(text, [str(item) for item in attachment_ids], "run")
    replay = await _replay(store, key, idempotency_key, fingerprint)
    if replay is not None:
        return replay, True
    conversation = create_conversation(store, key, slug)
    conversation_id = uuid.UUID(str(conversation["id"]))
    reply, _replayed = await send_message(
        store, key, slug, conversation_id, text, attachment_ids, ""
    )
    if idempotency_key:
        _remember_idempotency(
            store,
            key,
            idempotency_key,
            fingerprint,
            reply,
            uuid.UUID(str(reply["id"])),
            state="completed",
        )
        await _shared_put(store, key, idempotency_key, fingerprint, reply, done=True)
    return reply, False


def _attachment_names(store: Any, attachment_ids: list[uuid.UUID]) -> list[str]:
    names: list[str] = []
    for file_id in attachment_ids:
        row = store.files.get(file_id)
        if isinstance(row, dict):
            names.append(str(row.get("name") or "file"))
    return names


def owned_run(store: Any, key: dict[str, Any], slug: str, run_id: uuid.UUID) -> dict[str, Any]:
    """404 when the run belongs to another key, another agent, or another tenant."""
    agent = agent_for_key(store, key, slug)
    if not any(row.get("run_id") == run_id for row in _grants_for(store, key)):
        raise NotFoundError("run not found")
    run = store.runs.get(run_id)
    if not isinstance(run, dict) or run.get("tenant_id") != key.get("tenant_id"):
        raise NotFoundError("run not found")
    if run.get("agent_id") != agent.get("id"):
        raise NotFoundError("run not found")
    return run


def trace(store: Any, key: dict[str, Any], slug: str, run_id: uuid.UUID) -> dict[str, Any]:
    run = owned_run(store, key, slug, run_id)
    events = [
        event
        for event in store.events.get(run_id, [])
        if isinstance(event, dict) and event.get("run_id") in {str(run_id), run_id}
    ]
    calls = [
        {
            "id": str(row.get("id")),
            "qualified_name": str(row.get("qualified_name") or ""),
            "status": str(row.get("status") or ""),
            "policy_decision": str(row.get("policy_decision") or ""),
        }
        for row in store.tool_calls.values()
        if isinstance(row, dict) and row.get("run_id") == run_id
    ]
    body = _reply(store, run_id)
    body["events"] = events
    body["tool_calls"] = calls
    body["trace_id"] = str(run.get("trace_id") or "")
    return body


def bound_tool(definition: dict[str, Any], qualified: str) -> bool:
    server, _, name = qualified.partition(".")
    tools = definition.get("tools")
    if not isinstance(tools, list):
        return False
    for binding in tools:
        if not isinstance(binding, dict) or binding.get("server") != server:
            continue
        include = binding.get("include")
        names = include if isinstance(include, list) else ["*"]
        if "*" in names or name in names:
            return True
    return False


def find_tool_version(store: Any, qualified: str) -> dict[str, Any] | None:
    for version in store.tool_versions.values():
        if isinstance(version, dict) and version.get("qualified_name") == qualified:
            return version
    return None


def execute_write(
    store: Any,
    key: dict[str, Any],
    slug: str,
    qualified: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Run one bound tool through the policy gate. Approval comes back as a result."""
    from ar_domain.tools.pipeline import ToolPipeline  # noqa: PLC0415

    agent = agent_for_key(store, key, slug)
    if not take_quota(key):
        audit_key(
            store,
            tenant_id=key["tenant_id"],
            actor_id=_user_id(key),
            action="agent_api_call.refused",
            key_id=key["id"],
            label=str(key.get("label") or ""),
            outcome="failure",
            extra={"reason": "quota"},
        )
        raise ArError(ErrorCode.QUOTA_EXCEEDED, "monthly quota exceeded")
    if not bound_tool(definition_of(store, agent), qualified):
        raise NotFoundError("tool is not bound to this agent")
    version = find_tool_version(store, qualified)
    if version is None:
        raise NotFoundError("tool is not bound to this agent")
    created = create_conversation(store, key, slug)
    conversation_id = uuid.UUID(str(created["id"]))
    summary = str(arguments.get("summary") or qualified)
    posted = store.post_message(
        key["tenant_id"],
        _user_id(key),
        conversation_id,
        summary,
        schedule=False,
    )
    run = posted.get("run") if isinstance(posted, dict) else None
    run_id = uuid.UUID(str(run.get("id"))) if isinstance(run, dict) else new_id()
    _grant(store, key, agent, conversation_id, run_id)
    result = ToolPipeline(store).execute(
        {
            "tool_version_id": version["id"],
            "arguments": arguments,
            "tenant_id": key["tenant_id"],
            "user_id": _user_id(key),
            "agent_id": agent["id"],
            "agent_version_id": agent.get("published_version_id"),
            "run_id": run_id,
            "model_call_id": f"external-{run_id}",
        }
    )
    status = str(result.get("status") or "")
    approval_id = str(result.get("approval_id") or "")
    if status == "awaiting_approval" or result.get("policy_decision") == "require_approval":
        live = store.runs.get(run_id)
        if isinstance(live, dict):
            live["status"] = "waiting_approval"
            if approval_id:
                live["pending_approval"] = {"approval_id": uuid.UUID(approval_id)}
        audit_key(
            store,
            tenant_id=key["tenant_id"],
            actor_id=_user_id(key),
            action="agent_api_call.accepted",
            key_id=key["id"],
            label=str(key.get("label") or ""),
            extra={"path": "write", "run_id": str(run_id), "decision": "require_approval"},
        )
        return {
            "status": "approval_required",
            "output": "Approval required",
            "approval_id": approval_id,
            "run_id": str(run_id),
            "conversation_id": str(conversation_id),
            "tool": qualified,
        }
    if result.get("is_error") or status in {"failed", "denied"}:
        message = str(result.get("result_preview") or result.get("text") or "denied by policy")
        return {
            "status": "denied",
            "output": message,
            "run_id": str(run_id),
            "conversation_id": str(conversation_id),
            "tool": qualified,
        }
    return {
        "status": "completed",
        "output": str(result.get("result_preview") or ""),
        "run_id": str(run_id),
        "conversation_id": str(conversation_id),
        "tool": qualified,
        "structured": as_mapping(result.get("structured")),
    }
