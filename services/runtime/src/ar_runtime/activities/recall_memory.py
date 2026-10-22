"""Recall activity. Spec: docs/03-specs/11-memory.md §3."""

import uuid
from typing import TYPE_CHECKING, cast

from temporalio import activity

from ar_domain.agents.access import Actor
from ar_domain.memory.book import MemoryBook
from ar_domain.prompts.assembler import build_prompt

if TYPE_CHECKING:
    from typing import Any

_STORE: Any = None


def bind_store(store: Any) -> None:
    """Tests and the dev worker install the process store."""
    global _STORE  # noqa: PLW0603
    _STORE = store


@activity.defn(name="recall_memory")
async def recall_memory(payload: dict[str, object]) -> dict[str, object]:
    """Inject recalled facts into a prompt snapshot. Failure is an empty block."""
    store = _STORE
    run = payload.get("run")
    if store is None or not isinstance(run, dict):
        return {"memory": "", "count": 0, "prompt_hash": ""}
    tenant = run.get("tenant_id")
    user = run.get("user_id")
    if not isinstance(tenant, uuid.UUID) or not isinstance(user, uuid.UUID):
        return {"memory": "", "count": 0, "prompt_hash": ""}
    raw_definition = run.get("definition")
    definition = (
        cast("dict[str, object]", raw_definition) if isinstance(raw_definition, dict) else {}
    )
    actor = Actor(tenant, user, frozenset({"chat:use"}))
    block, facts = MemoryBook(store).prompt_block(
        actor,
        query=str(payload.get("query") or ""),
        agent_id=run.get("agent_id") if isinstance(run.get("agent_id"), uuid.UUID) else None,
        definition=definition,
    )
    bundle = build_prompt(
        {
            "definition": definition,
            "user_text": str(payload.get("query") or ""),
            "memory": block,
            "summary": str(run.get("summary") or ""),
            "history": run.get("history") if isinstance(run.get("history"), list) else [],
        }
    )
    return {
        "memory": block,
        "count": len(facts),
        "fact_ids": [str(fact.get("id")) for fact in facts],
        "prompt_hash": bundle.prompt_hash,
        "messages": [dict(item) for item in bundle.messages],
    }
