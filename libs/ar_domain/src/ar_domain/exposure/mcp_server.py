"""Streamable HTTP MCP server. One tool per published agent the key may call."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import ArError, NotFoundError
from ar_domain.exposure.runs import (
    create_conversation,
    definition_of,
    execute_write,
    published_agent,
    send_message,
)

if TYPE_CHECKING:
    from typing import Any

_PROTOCOL = "2025-03-26"


def listed_agents(store: Any, key: dict[str, Any]) -> list[dict[str, Any]]:
    tenant_id = key.get("tenant_id")
    if not isinstance(tenant_id, uuid.UUID):
        return []
    if str(key.get("scope") or "agent") == "workspace":
        found: list[dict[str, Any]] = []
        for agent in store.agents.values():
            if not isinstance(agent, dict) or agent.get("tenant_id") != tenant_id:
                continue
            if str(agent.get("status") or "") not in {"published", "active"}:
                continue
            if agent.get("disabled") or agent.get("published_version_id") is None:
                continue
            found.append(agent)
        found.sort(key=lambda item: str(item.get("slug") or ""))
        return found
    agent_id = key.get("agent_id")
    agent = store.agents.get(agent_id) if isinstance(agent_id, uuid.UUID) else None
    if not isinstance(agent, dict):
        return []
    try:
        return [published_agent(store, tenant_id, str(agent.get("slug") or ""))]
    except NotFoundError, ArError:
        return []


def _research_tool() -> dict[str, Any]:
    return {
        "name": "research",
        "description": "Search, read pages and return a report whose claims cite stored sources.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to research.",
                }
            },
            "required": ["question"],
        },
    }


def tool_name(slug: str) -> str:
    return "agent_" + slug.replace("-", "_")


def _slug_from_tool(name: str, agents: list[dict[str, Any]]) -> str | None:
    for agent in agents:
        slug = str(agent.get("slug") or "")
        if tool_name(slug) == name:
            return slug
    return None


def tools_list(store: Any, key: dict[str, Any]) -> dict[str, Any]:
    tools = []
    for agent in listed_agents(store, key):
        definition = definition_of(store, agent)
        raw_contract = definition.get("contract")
        contract = raw_contract if isinstance(raw_contract, dict) else {}
        description = str(
            contract.get("description") or agent.get("description") or agent.get("name")
        )
        tools.append(
            {
                "name": tool_name(str(agent.get("slug") or "")),
                "description": description or str(agent.get("name") or "Agent"),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message for the agent."},
                        "conversation_id": {"type": "string"},
                        "write": {
                            "type": "object",
                            "description": (
                                "A write this agent may perform. Approval is returned, not skipped."
                            ),
                            "properties": {
                                "tool": {"type": "string"},
                                "arguments": {"type": "object"},
                            },
                            "required": ["tool"],
                        },
                    },
                },
            }
        )
    tools.append(_research_tool())
    return {"tools": tools}


async def tools_call(
    store: Any, key: dict[str, Any], name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    if name == "research":
        return await _research_call(store, key, arguments)
    agents = listed_agents(store, key)
    slug = _slug_from_tool(name, agents)
    if slug is None:
        return _error("unknown tool")
    write = arguments.get("write")
    if isinstance(write, dict) and write.get("tool"):
        raw_args = write.get("arguments")
        outcome = execute_write(
            store,
            key,
            slug,
            str(write.get("tool")),
            raw_args if isinstance(raw_args, dict) else {},
        )
        return _from_write(outcome)
    text = str(arguments.get("message") or "").strip()
    if not text:
        return _error("message is required")
    conversation = arguments.get("conversation_id")
    if conversation:
        conversation_id = uuid.UUID(str(conversation))
    else:
        created = create_conversation(store, key, slug)
        conversation_id = uuid.UUID(str(created["id"]))
    body, _replayed = await send_message(store, key, slug, conversation_id, text, [], "")
    return _from_message(body)


def _from_write(outcome: dict[str, Any]) -> dict[str, Any]:
    status = str(outcome.get("status") or "")
    if status == "approval_required":
        return {
            "content": [{"type": "text", "text": "Approval required"}],
            "is_error": False,
            "structured_content": {
                "status": "approval_required",
                "approval_id": outcome.get("approval_id") or "",
                "run_id": outcome.get("run_id") or "",
            },
        }
    failed = status == "denied"
    return {
        "content": [{"type": "text", "text": str(outcome.get("output") or "")}],
        "is_error": failed,
        "structured_content": {"status": status, "run_id": outcome.get("run_id") or ""},
    }


def _from_message(body: dict[str, Any]) -> dict[str, Any]:
    finish = str(body.get("finish_reason") or "")
    if finish == "approval_required":
        return {
            "content": [{"type": "text", "text": "Approval required"}],
            "is_error": False,
            "structured_content": {
                "status": "approval_required",
                "approval_id": body.get("approval_id") or "",
                "run_id": body.get("id") or "",
            },
        }
    parts = body.get("content")
    public_parts = (
        [part for part in parts if isinstance(part, dict)] if isinstance(parts, list) else []
    )
    extra = [part for part in public_parts if part.get("type") not in {"text", "reasoning"}]
    return {
        "content": [{"type": "text", "text": str(body.get("output") or "")}, *extra],
        "is_error": finish in {"failed", "cancelled"},
        "structured_content": {
            "status": body.get("status") or finish,
            "run_id": body.get("id") or "",
            "conversation_id": body.get("conversation_id") or "",
            "content": public_parts,
        },
    }


async def _research_call(
    store: Any, key: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    question = str(arguments.get("question") or "").strip()
    if not question:
        return _error("question is required")
    agents = listed_agents(store, key)
    if not agents:
        return _error("no published agent")
    slug = str(agents[0].get("slug") or "")
    created = create_conversation(store, key, slug)
    conversation_id = uuid.UUID(str(created["id"]))
    body, _replayed = await send_message(
        store, key, slug, conversation_id, question, [], "", research=True
    )
    return _from_message(body)


def _error(text: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "is_error": True,
        "structured_content": {"status": "error"},
    }


def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    del params
    return {
        "protocol_version": _PROTOCOL,
        "capabilities": {"tools": {"list_changed": False}},
        "server_info": {"name": "agentic-runtime", "version": "1"},
    }


async def handle_rpc(
    store: Any, key: dict[str, Any], message: dict[str, Any]
) -> dict[str, Any] | None:
    """One JSON-RPC message. A notification (no id) returns None."""
    method = str(message.get("method") or "")
    request_id = message.get("id")
    raw_params = message.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    if method == "notifications/initialized":
        return None
    if request_id is None and method.startswith("notifications/"):
        return None
    try:
        result = await _dispatch(store, key, method, params)
    except Exception as exc:  # noqa: BLE001 — MCP clients receive a JSON-RPC error
        return _rpc_error(request_id, -32000, str(exc) or "request failed")
    if result is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


async def _dispatch(
    store: Any, key: dict[str, Any], method: str, params: dict[str, Any]
) -> dict[str, Any] | None:
    if method == "initialize":
        return handle_initialize(params)
    if method == "ping":
        return {}
    if method == "tools/list":
        return tools_list(store, key)
    if method == "tools/call":
        name = str(params.get("name") or "")
        raw_arguments = params.get("arguments")
        arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
        return await tools_call(store, key, name, arguments)
    raise ValueError(f"method not found: {method}")


def _rpc_error(request_id: object, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
