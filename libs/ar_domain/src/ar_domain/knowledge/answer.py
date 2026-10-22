"""Grounded answers for agents with ``knowledge.auto_retrieve``."""

import uuid
from typing import TYPE_CHECKING

from ar_domain.agents.access import Actor
from ar_domain.identity.permissions import PERMISSION_KEYS, SYSTEM_ROLE_PERMISSIONS
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.citations import allocate, content_parts, known_indexes
from ar_domain.knowledge.grounding import apply_grounding

if TYPE_CHECKING:
    from typing import Any


def compose(store: Any, run: dict[str, object], question: str) -> dict[str, object] | None:
    """Return an answer when the published agent retrieves automatically."""
    definition = _definition(store, run)
    knowledge = definition.get("knowledge") if isinstance(definition, dict) else None
    if not isinstance(knowledge, dict) or knowledge.get("auto_retrieve") is not True:
        return None
    actor = _actor(store, run)
    slugs = {str(item) for item in knowledge.get("collections") or []}
    ids = [
        row["id"]
        for row in store.knowledge_collections.values()
        if row.get("tenant_id") == actor.tenant_id and str(row.get("slug")) in slugs
    ]
    if not ids:
        text = "No sufficiently relevant documents were found."
        return _pack(text, [], definition, question)
    if not _policy_allows(store, run, question, ids):
        text = "No sufficiently relevant documents were found."
        return _pack(text, [], definition, question)
    top_k = int(knowledge.get("top_k") or 8)
    min_score = float(knowledge.get("min_score") or 0.2)
    found = KnowledgeBook(store).search(
        actor,
        {
            "query": question,
            "collection_ids": ids,
            "top_k": min(top_k, 20),
            "min_score": min_score,
        },
    )
    hits = found.get("hits") if isinstance(found.get("hits"), list) else []
    if not found.get("answerable"):
        return _pack("No sufficiently relevant documents were found.", [], definition, question)
    citations = allocate([hit for hit in hits if isinstance(hit, dict)])  # type: ignore[attr-defined]
    sentences = [
        f"{str(item.get('snippet') or '').strip()} [{item['index']}]"
        for item in citations
        if str(item.get("snippet") or "").strip()
    ]
    return _pack(" ".join(sentences), citations, definition, question)


def _pack(
    text: str,
    citations: list[dict[str, object]],
    definition: dict[str, object],
    question: str,
) -> dict[str, object]:
    output = definition.get("output") if isinstance(definition.get("output"), dict) else {}
    mode = str(output.get("grounding") or "off") if isinstance(output, dict) else "off"
    visible, report = apply_grounding(text, known_indexes(citations), mode=mode)
    parts = content_parts(visible, citations)
    if report is not None:
        report["sources"] = citations
        report["question"] = question[:200]
        parts.append({"type": "grounding", "report": report})
    return {"text": visible, "citations": citations, "parts": parts, "report": report}


def _definition(store: Any, run: dict[str, object]) -> dict[str, object]:
    version_id = run.get("agent_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    if not isinstance(version, dict):
        return {}
    definition = version.get("definition")
    return definition if isinstance(definition, dict) else {}


def _actor(store: Any, run: dict[str, object]) -> Actor:
    raw_user = run.get("user_id")
    raw_tenant = run.get("tenant_id")
    user_id = raw_user if isinstance(raw_user, uuid.UUID) else uuid.UUID(str(raw_user))
    tenant_id = raw_tenant if isinstance(raw_tenant, uuid.UUID) else uuid.UUID(str(raw_tenant))
    roles = set(getattr(store, "user_roles", {}).get(user_id, set()))
    if "tenant_admin" in roles:
        permissions = PERMISSION_KEYS
    else:
        permissions = set()  # type: ignore[assignment]
        for role in roles:
            permissions.update(SYSTEM_ROLE_PERMISSIONS.get(role, ()))  # type: ignore[attr-defined]
        permissions.add("knowledge:read")  # type: ignore[attr-defined]
    return Actor(tenant_id, user_id, frozenset(permissions), roles=frozenset(roles))


def _policy_allows(store: Any, run: dict[str, object], question: str, ids: list[object]) -> bool:
    version = None
    for row in getattr(store, "tool_versions", {}).values():
        if row.get("qualified_name") == "knowledge.search":
            version = row
            break
    if not isinstance(version, dict):
        return True
    from ar_domain.tools.pipeline import ToolPipeline  # noqa: PLC0415

    outcome = ToolPipeline(store).execute(
        {
            "tenant_id": run.get("tenant_id"),
            "user_id": run.get("user_id"),
            "tool_version_id": version.get("id"),
            "agent_version_id": run.get("agent_version_id"),
            "run_id": run.get("id"),
            "arguments": {"query": question, "collection_ids": [str(item) for item in ids]},
        }
    )
    return outcome.get("status") != "denied"
