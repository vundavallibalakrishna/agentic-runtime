"""Hook memory into an in-process run. Spec: docs/03-specs/07-agent-runtime.md §2."""

import uuid
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from ar_domain.agents.access import Actor
from ar_domain.files.attachments import Attachment, attachment_lines, conversation_attachments
from ar_domain.memory.book import MemoryBook
from ar_domain.memory.compaction import compact_context, needs_compaction
from ar_domain.prompts.assembler import build_prompt, with_attachments


def prepare_prompt(
    store: Any,
    run: dict[str, object],
    conversation: dict[str, object],
    definition: dict[str, object],
    text: str,
) -> str:
    """Recall memory, compact when needed, and return the prompt hash.

    Each message is shown with the files attached to it, so a later turn still knows a
    file an earlier message brought.
    """
    from ar_domain.documents.binding import context_window_for  # noqa: PLC0415

    window = context_window_for(store, run.get("tenant_id"), run) if isinstance(run, dict) else None
    attached: dict[object, list[Attachment]] = {}
    for item in conversation_attachments(store, conversation.get("id"), context_window=window):
        attached.setdefault(item.message_id, []).append(_safe(store, run, item))
    history = _history(store, conversation.get("id"), run.get("input_message_id"), attached)
    window = window or _window(definition)
    threshold = _threshold(definition)
    keep = _keep(definition)
    joined = "\n".join(str(item.get("content") or "") for item in history) + "\n" + text
    prompt_history = history
    if needs_compaction(joined, context_window=window, threshold=threshold):
        compacted = compact_context(
            history, context_window=window, threshold=threshold, keep_messages=keep
        )
        if compacted.get("summary"):
            conversation["rolling_summary"] = compacted["summary"]
            conversation["summary_through_message_id"] = compacted["summary_through_message_id"]
            kept = compacted.get("messages")
            if isinstance(kept, list) and not compacted.get("error"):
                prompt_history = [dict(item) for item in kept if isinstance(item, dict)]
        run["compaction"] = {
            "tokens_before": compacted["tokens_before"],
            "tokens_after": compacted["tokens_after"],
            "error": compacted["error"],
            "strategy": "summary",
            "keep_messages": keep,
        }
        if compacted.get("error") == "context_length_exceeded":
            run["context_error"] = "context_length_exceeded"
    actor = _actor(run)
    block, facts = MemoryBook(store).prompt_block(
        actor,
        query=text,
        agent_id=_uuid(run.get("agent_id")),
        definition=definition,
    )
    run["memory"] = block
    run["recalled"] = [dict(item) for item in facts]
    from ar_domain.skills.sections import capabilities_block, loaded_skills_block  # noqa: PLC0415

    tenant = run.get("tenant_id")
    run["capabilities"] = capabilities_block(
        store, definition, tenant_id=tenant if isinstance(tenant, uuid.UUID) else None
    )
    run["skills"] = loaded_skills_block(store, conversation, run)
    from ar_domain.config_docs.book import agent_settings_block  # noqa: PLC0415

    run["agent_settings"] = agent_settings_block(store, run)
    bundle = build_prompt(
        {
            "definition": definition,
            "user_text": text,
            "agent_settings": run["agent_settings"],
            "channel": str(conversation.get("channel") or ""),
            "files": _files_block(store, run, definition, attached),
            "history": prompt_history,
            "memory": block,
            "summary": str(conversation.get("rolling_summary") or ""),
            "documents": run.get("documents"),
            "capabilities": run["capabilities"],
            "skills": run["skills"],
        }
    )
    run["prompt_messages"] = [dict(item) for item in bundle.messages]
    return bundle.prompt_hash


def _safe(store: Any, run: dict[str, object], item: Attachment) -> Attachment:
    """The attachment, with its text as a document tool would return it."""
    if not item.excerpt:
        return item
    return replace(item, excerpt=_safe_text(store, run, item.excerpt))


def _safe_text(store: Any, run: object, text: str) -> str:
    """File text as it may enter a prompt.

    A file's text reaches the model two ways: a document tool returns it, or the turn
    shows it beside the message. Both pass through the same masking, so an agent or a
    tenant that asks for document text to be masked gets it masked on both.
    """
    if not text or not isinstance(run, dict):
        return text
    from ar_domain.security.guardrails import apply_result_safety  # noqa: PLC0415

    tenant = run.get("tenant_id")
    version = run.get("agent_version_id")
    cleaned, _flag = apply_result_safety(
        store,
        text,
        open_world=False,
        analysis=True,
        tenant_id=tenant if isinstance(tenant, uuid.UUID) else None,
        agent_version_id=version if isinstance(version, uuid.UUID) else None,
    )
    return cleaned


def _files_block(
    store: Any,
    run: dict[str, object],
    definition: dict[str, object],
    attached: dict[object, list[Attachment]],
) -> str:
    """Files on this turn, the agent's default files, and a section reduction."""
    lines = attachment_lines(attached.get(run.get("input_message_id"), []))
    known = {item.file_id for rows in attached.values() for item in rows}
    extra = _agent_lines(store, run, definition, known)
    reduction = run.get("document_reduction")
    facts = _fact_lines(run)
    parts = [
        part
        for part in (facts, lines, extra, reduction if isinstance(reduction, str) else "")
        if part
    ]
    return "\n".join(parts)


def _agent_lines(
    store: Any,
    run: dict[str, object],
    definition: dict[str, object],
    known: set[uuid.UUID],
) -> str:
    knowledge = definition.get("knowledge")
    raw = (
        knowledge.get("file_ids", knowledge.get("fileIds")) if isinstance(knowledge, dict) else None
    )
    if not isinstance(raw, list):
        return ""
    from ar_domain.documents.binding import context_window_for  # noqa: PLC0415
    from ar_domain.files.attachments import _library_excerpt  # noqa: PLC0415

    window = context_window_for(store, run.get("tenant_id"), run)
    files = getattr(store, "files", {})
    lines: list[str] = []
    if not isinstance(files, dict):
        return ""
    for item in raw:
        try:
            file_id = uuid.UUID(str(item))
        except ValueError:
            continue
        if file_id in known:
            continue
        meta = files.get(file_id)
        if not isinstance(meta, dict) or meta.get("tenant_id") != run.get("tenant_id"):
            continue
        if meta.get("owner_user_id") is None:
            continue
        if meta.get("owner_user_id") != run.get("user_id") and not _bound_to_agent(
            definition, file_id
        ):
            continue
        _document_id, excerpt = _library_excerpt(store, meta, context_window=window)
        excerpt = _safe_text(store, run, excerpt)
        lines.append(f"[file: {meta.get('name')} id={file_id}]\n{excerpt}".strip())
    return "\n".join(lines)


def _history(
    store: Any,
    conversation_id: object,
    skip: object,
    attached: dict[object, list[Attachment]],
) -> list[dict[str, str]]:
    rows: list[dict[str, object]] = []
    messages = getattr(store, "messages", {})
    if not isinstance(messages, dict):
        return []
    for message in messages.values():
        if not isinstance(message, dict):
            continue
        if message.get("conversation_id") != conversation_id or message.get("id") == skip:
            continue
        if message.get("role") not in {"user", "assistant", "tool"}:
            continue
        if message.get("status") not in {None, "completed"}:
            continue
        if message.get("scope") == "run":
            # What a lead and a specialist said to each other is not what the person said.
            continue
        rows.append(message)
    rows.sort(key=lambda item: str(item.get("created_at") or ""))
    return [
        {
            "id": str(message.get("id") or ""),
            "role": str(message.get("role") or "user"),
            "content": with_attachments(
                str(message.get("text") or ""),
                attachment_lines(attached.get(message.get("id"), [])),
            ),
        }
        for message in rows
    ]


def _actor(run: dict[str, object]) -> Actor:
    return Actor(
        tenant_id=_uuid(run.get("tenant_id")) or uuid.UUID(int=0),
        user_id=_uuid(run.get("user_id")) or uuid.UUID(int=0),
        permissions=frozenset({"chat:use"}),
    )


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    return None


def _window(definition: dict[str, object]) -> int:
    raw = definition.get("context_window")
    if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
        return raw
    from ar_common.settings import get_settings  # noqa: PLC0415

    return int(get_settings().default_context_window)


def _fact_lines(run: dict[str, object]) -> str:
    raw = run.get("document_facts")
    if not isinstance(raw, list) or not raw:
        return ""
    lines = ["Measured documents:"]
    for item in raw:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('title') or item.get('fileId')} file={item.get('fileId')} "
            f"document={item.get('documentId')} tokens={item.get('tokens')} "
            f"pages={item.get('pages')} outline={item.get('outline')} "
            f"tables={item.get('tables')} fits={str(item.get('fits')).lower()}"
        )
    return "\n".join(lines)


def _bound_to_agent(definition: dict[str, object], file_id: uuid.UUID) -> bool:
    knowledge = definition.get("knowledge")
    raw = (
        knowledge.get("file_ids", knowledge.get("fileIds")) if isinstance(knowledge, dict) else None
    )
    if not isinstance(raw, list):
        return False
    return str(file_id) in {str(item) for item in raw}


def _keep(definition: dict[str, object]) -> int:
    context = definition.get("context")
    if isinstance(context, dict):
        raw = context.get("keep_messages", context.get("keepMessages", 12))
        if isinstance(raw, int) and not isinstance(raw, bool) and 2 <= raw <= 40:
            return raw
    return 12


def _threshold(definition: dict[str, object]) -> float:
    context = definition.get("context")
    if isinstance(context, dict):
        raw = context.get("compaction_threshold", context.get("compactionThreshold", 0.7))
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
    return 0.7
