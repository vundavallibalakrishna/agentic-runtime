"""The console's tool test: one tool call with the arguments a person typed.

The API checks what only it can check, that the person may see the tool and owns the
conversation, and builds the request. The call itself runs where every tool call runs:
in the tool gateway in staging and production, in this process in dev and in a test.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.ids import new_id
from ar_domain.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from typing import Any


def console_request(
    store: Any,
    who: Any,
    tool_id: uuid.UUID,
    *,
    arguments: dict[str, object],
    dry_run: bool,
    conversation_id: uuid.UUID | None,
) -> dict[str, object]:
    """The test as a tool-call request. Raises not-found for a tool or conversation
    the caller may not see."""
    detail = ToolRegistry(store).get_tool(who, tool_id)
    if conversation_id is not None:
        # Another tenant's or another person's conversation is not found.
        store._conversation(who.tenant_id, who.user_id, conversation_id, read_all=False)
    return {
        "tenant_id": who.tenant_id,
        "user_id": who.user_id,
        "run_id": new_id(),
        "conversation_id": conversation_id,
        "synthetic": True,
        "tool_version_id": uuid.UUID(str(detail["tool_version_id"])),
        "arguments": arguments,
        "permissions": sorted(who.permissions),
        "dry_run": dry_run,
        "model_call_id": "test",
    }


def open_console_run(store: Any, request: dict[str, object]) -> dict[str, object]:
    """Store the run the test's tool call belongs to, and name its agent in the request.

    A console test still has to reference a real agent version. A run with no agent is
    skipped on flush, and the tool-call row then violates the run foreign key and fails
    every later save. A test in a conversation runs as that conversation's agent: its
    computer template and its tool settings, as a turn there would.
    """
    tenant_id = request.get("tenant_id")
    conversation_id = request.get("conversation_id")
    agent = _console_agent(store, tenant_id)
    talk = getattr(store, "conversations", {}).get(conversation_id)
    if isinstance(talk, dict) and talk.get("tenant_id") == tenant_id:
        owner = talk.get("agent_id")
        agent = (store.agents.get(owner) if isinstance(owner, uuid.UUID) else None) or agent
    agent_id = None if agent is None else agent.get("id")
    version_id = None if agent is None else agent.get("published_version_id")
    run_id = request.get("run_id") or new_id()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": tenant_id,
        "user_id": request.get("user_id"),
        "conversation_id": conversation_id if isinstance(talk, dict) else None,
        "agent_id": agent_id,
        "trigger": "api",
        "depth": 0,
        "root_run_id": run_id,
        "synthetic": True,
        "status": "completed",
    }
    return {
        **request,
        "run_id": run_id,
        "agent_id": agent_id,
        "agent_version_id": version_id if isinstance(version_id, uuid.UUID) else None,
        "synthetic": True,
    }


def _console_agent(store: Any, tenant_id: object) -> dict[str, object] | None:
    """An agent this tenant already published, so the console run can be stored."""
    agents = getattr(store, "agents", None)
    if not isinstance(agents, dict):
        return None
    for row in agents.values():
        if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
            continue
        if row.get("published_version_id") or row.get("draft_version_id"):
            return row
    return None
