"""Build the model prompt for one live turn.

History and the rolling summary come from the conversation. Memory facts that
were recalled are already in that prompt. This module adds a matched skill and
the knowledge passages that fit the character budget, and records both on the run.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.wrapping import wrap_untrusted
from ar_domain.agents.access import Actor
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.models.embedding import EmbeddingFailedError, EmbeddingUnconfiguredError
from ar_domain.prompts.assembler import build_prompt
from ar_domain.skills.match import match_skill

if TYPE_CHECKING:
    from typing import Any

_NO_LIBRARY = (
    "No knowledge base is attached to this turn. "
    "If the question depends on the user's documents, say you do not have them. "
    "Do not invent a citation, a page number, or a private code."
)


def has_grounding(definition: dict[str, object]) -> bool:
    """True when the agent has a knowledge base or at least one skill."""
    return bool(_collection_ids(None, definition)) or bool(_skill_names(definition))


async def ground_run(store: Any, run: dict[str, object], user_text: str) -> None:
    """Attach retrieval and a loaded skill to the run and to its system prompt."""
    definition = _definition(store, run)
    if definition is None:
        return
    skill = match_skill(store, run, definition, user_text)
    retrieval = await _retrieve(store, run, definition, user_text)
    if skill is not None:
        run["loaded_skill"] = {
            "slug": skill["slug"],
            "name": skill["name"],
            "reason": skill["reason"],
            "version": skill.get("version"),
        }
    if retrieval is not None:
        run["retrieval"] = retrieval["trace"]
    _append_system(run, definition, skill, retrieval)


def opening_messages(
    run: dict[str, object], definition: dict[str, object], user_text: str
) -> list[dict[str, object]]:
    """The messages a turn starts with.

    A chat turn has its prompt prepared, with history, memory and compaction. A run that
    starts without one, such as a child run another agent called, gets the same system
    blocks from the same builder: platform rules, tool guidance, the agent's
    instructions and its output schema.
    """
    prepared = run.get("prompt_messages")
    if isinstance(prepared, list) and prepared:
        return [dict(item) for item in prepared if isinstance(item, dict)]
    bundle = build_prompt({"definition": definition, "user_text": user_text})
    return [dict(item) for item in bundle.messages]


def citation_parts(retrieval: object) -> list[dict[str, object]]:
    """Citation cards for the chunks that were actually placed in the prompt."""
    if not isinstance(retrieval, dict):
        return []
    hits = retrieval.get("hits")
    if not isinstance(hits, list):
        return []
    parts: list[dict[str, object]] = []
    for index, hit in enumerate(hits, start=1):
        if not isinstance(hit, dict):
            continue
        document_id = str(hit.get("document_id") or "")
        anchor = str(hit.get("anchor") or "")
        library_id = str(hit.get("library_document_id") or "")
        uri = f"/documents/{library_id}#{anchor}" if library_id and anchor else ""
        parts.append(
            {
                "type": "citation_ref",
                "index": index,
                "citation": {
                    "index": index,
                    "title": hit.get("title") or "Source",
                    "snippet": hit.get("snippet") or "",
                    "uri": uri or str(hit.get("anchor") or ""),
                    "document_id": library_id or document_id,
                    "anchor": anchor,
                    "page": hit.get("page"),
                },
            }
        )
    return parts


async def _retrieve(
    store: Any, run: dict[str, object], definition: dict[str, object], user_text: str
) -> dict[str, object] | None:
    from ar_domain.knowledge.members import retrieve  # noqa: PLC0415

    tenant = run.get("tenant_id")
    user = run.get("user_id")
    if not isinstance(tenant, uuid.UUID) or not isinstance(user, uuid.UUID):
        return None
    slugs = _collection_slugs(definition)
    if not slugs:
        return None
    ids = [
        row["id"]
        for row in getattr(store, "knowledge_collections", {}).values()
        if isinstance(row, dict)
        and row.get("tenant_id") == tenant
        and str(row.get("slug")) in slugs
        and isinstance(row.get("id"), uuid.UUID)
    ]
    if not ids:
        return {"hits": [], "trace": {"query": user_text[:500], "hits": [], "used_chars": 0}}
    actor = Actor(tenant, user, PERMISSION_KEYS)
    try:
        return await retrieve(store, actor, ids, user_text)
    except (EmbeddingUnconfiguredError, EmbeddingFailedError) as exc:
        return {
            "hits": [],
            "trace": {
                "query": user_text[:500],
                "hits": [],
                "used_chars": 0,
                "warning": str(exc),
            },
        }


def _append_system(
    run: dict[str, object],
    definition: dict[str, object],
    skill: dict[str, object] | None,
    retrieval: dict[str, object] | None,
) -> None:
    messages = run.get("prompt_messages")
    if not isinstance(messages, list) or not messages:
        messages = [{"role": "system", "content": str(definition.get("instructions") or "")}]
        run["prompt_messages"] = messages
    system = messages[0] if isinstance(messages[0], dict) else {"role": "system", "content": ""}
    if system.get("role") != "system":
        system = {"role": "system", "content": ""}
        messages.insert(0, system)
    extra: list[str] = []
    if skill is not None:
        extra.append(
            "A skill was loaded because "
            f"{skill['reason']}. Follow these instructions:\n{skill['instructions']}"
        )
    hits = retrieval.get("hits") if isinstance(retrieval, dict) else None
    if isinstance(hits, list) and hits:
        blocks = []
        for index, hit in enumerate(hits, start=1):
            if not isinstance(hit, dict):
                continue
            text = str(hit.get("text") or hit.get("snippet") or "")
            anchor = hit.get("anchor") or ""
            page = hit.get("page") or ""
            blocks.append(f"[{index}] {hit.get('title')} anchor={anchor} page={page}\n{text}")
        wrapped = wrap_untrusted(source="knowledge", content="\n\n".join(blocks))
        extra.append(
            "Answer from the knowledge passages. Cite the anchor in brackets. "
            "If the passages do not contain the answer, say it was not found.\n"
            f"{wrapped}"
        )
    else:
        extra.append(_NO_LIBRARY)
    if extra:
        system["content"] = str(system.get("content") or "") + "\n\n" + "\n\n".join(extra)


def _definition(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    version_id = run.get("agent_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    if not isinstance(version, dict):
        return None
    definition = version.get("definition")
    return definition if isinstance(definition, dict) else None


def _collection_slugs(definition: dict[str, object]) -> set[str]:
    knowledge = definition.get("knowledge")
    if not isinstance(knowledge, dict):
        return set()
    raw = knowledge.get("collections") or []
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if str(item).strip()}


def _collection_ids(store: object, definition: dict[str, object]) -> set[str]:
    del store
    return _collection_slugs(definition)


def _skill_names(definition: dict[str, object]) -> list[str]:
    raw = definition.get("skills")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]
