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

_LIBRARY_MISS = (
    "The library does not contain the answer to this question. "
    "Say that in those words. Do not invent a citation, a page number, or an answer "
    "from knowledge that was not retrieved."
)
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
    bundle = build_prompt(
        {
            "definition": definition,
            "user_text": user_text,
            "agent_settings": str(run.get("agent_settings") or ""),
        }
    )
    return [dict(item) for item in bundle.messages]


def citation_parts(retrieval: object, answer: str | None = None) -> list[dict[str, object]]:
    """Citation cards for the passages the run placed before the model.

    Passages are numbered once per run, those placed in the prompt first and those a
    search found later after them. When ``answer`` cites any of them with ``[n]``, the
    cards are the ones it cites (spec 07 §Citations); an answer that cites none gets a
    card for each passage it was given, so a reader still sees its sources.
    """
    if not isinstance(retrieval, dict):
        return []
    hits = retrieval.get("hits")
    if not isinstance(hits, list):
        return []
    from ar_domain.knowledge.grounding import cited_indexes  # noqa: PLC0415

    cited = {index for index in cited_indexes(answer or "") if 1 <= index <= len(hits)}
    parts: list[dict[str, object]] = []
    for index, hit in enumerate(hits, start=1):
        if not isinstance(hit, dict) or (cited and index not in cited):
            continue
        document_id = str(hit.get("document_id") or "")
        anchor = str(hit.get("anchor") or "")
        library_id = str(hit.get("library_document_id") or "")
        # A passage of a library document opens in the library. One read from an address,
        # such as a page of a website, opens at that address.
        uri = f"/documents/{library_id}#{anchor}" if library_id and anchor else ""
        uri = uri or str(hit.get("uri") or "")
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
    from ar_domain.runs.request import asked  # noqa: PLC0415

    named = asked(run, "collection_ids")
    slugs = _collection_slugs(definition)
    ids = [
        row["id"]
        for row in getattr(store, "knowledge_collections", {}).values()
        if isinstance(row, dict)
        and row.get("tenant_id") == tenant
        and isinstance(row.get("id"), uuid.UUID)
        and (
            (isinstance(named, list) and str(row.get("id")) in {str(item) for item in named})
            or (not named and str(row.get("slug")) in slugs)
        )
    ]
    if not ids:
        if not named and not slugs:
            return None
        return {"hits": [], "trace": {"query": user_text[:500], "hits": [], "used_chars": 0}}
    from ar_domain.knowledge.threshold import retrieval_bar  # noqa: PLC0415

    actor = Actor(tenant, user, PERMISSION_KEYS)
    try:
        return await retrieve(
            store,
            actor,
            ids,
            user_text,
            top_k=_top_k(definition),
            min_score=retrieval_bar(store, tenant, definition),
        )
    except (EmbeddingUnconfiguredError, EmbeddingFailedError) as exc:
        detail = str(exc.detail or exc)
        emit = getattr(store, "_emit", None)
        if callable(emit):
            emit(
                run,
                "warning",
                {"code": "embedding_unconfigured", "message": detail},
            )
        return {
            "hits": [],
            "trace": {
                "query": user_text[:500],
                "hits": [],
                "used_chars": 0,
                "error": detail,
                "code": "embedding_unconfigured",
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
            f"The '{skill['name']}' skill looks relevant ({skill['reason']}). "
            "Load it with skills.load to follow its instructions."
        )
    hits = retrieval.get("hits") if isinstance(retrieval, dict) else None
    trace = retrieval.get("trace") if isinstance(retrieval, dict) else None
    retrieval_error = trace.get("error") if isinstance(trace, dict) else None
    if retrieval_error:
        extra.append(
            "Knowledge retrieval failed: "
            + str(retrieval_error)
            + " Do not invent passages, citations, or page numbers."
        )
    elif isinstance(hits, list) and hits:
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
            "Answer from the knowledge passages. After each claim, cite the number of the "
            "passage it comes from in brackets, like [2]. Passages a search finds later "
            "carry their own numbers; cite those the same way. "
            "If the passages do not contain the answer, say it was not found.\n"
            f"{wrapped}"
        )
    elif isinstance(retrieval, dict) and _collection_slugs(definition):
        extra.append(_LIBRARY_MISS)
    else:
        extra.append(_NO_LIBRARY)
    rule = length_rule(definition)
    if rule:
        # Last, after the passages and right before the question: a rule at the top of a
        # long prompt was ignored (26 of 36 answers ran past a 120-word limit).
        extra.append(rule)
    if extra:
        system["content"] = str(system.get("content") or "") + "\n\n" + "\n\n".join(extra)


def max_words(definition: dict[str, object] | None) -> int | None:
    """``output.maxWords`` when the agent sets one."""
    output = definition.get("output") if isinstance(definition, dict) else None
    raw = output.get("max_words", output.get("maxWords")) if isinstance(output, dict) else None
    return raw if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0 else None


def length_rule(definition: dict[str, object] | None) -> str:
    """The answer-length rule the model reads last, or empty when the agent sets none."""
    words = max_words(definition)
    if words is None:
        return ""
    return (
        f"Length: your answer is at most {words} words. Lead with the direct answer, keep "
        "only what the question needs, and keep each citation. When the question asks for "
        "more than fits, cover the most important parts and say what you left out."
    )


def _definition(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    version_id = run.get("agent_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    if not isinstance(version, dict):
        return None
    definition = version.get("definition")
    return definition if isinstance(definition, dict) else None


def _top_k(definition: dict[str, object]) -> int:
    """How many passages one query may bring: the agent's own ``knowledge.topK``."""
    from ar_contracts.definitions import KnowledgeSpec  # noqa: PLC0415

    knowledge = definition.get("knowledge")
    raw = knowledge.get("top_k") if isinstance(knowledge, dict) else None
    default = int(KnowledgeSpec.model_fields["top_k"].default)
    return raw if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0 else default


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
