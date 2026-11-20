"""Name stored files on a turn and remember that the turn did.

File parts are written on the user message. A later turn finds them without
the caller sending the ids again. The audit row records ids, the task, the
strategy and byte sizes. It does not record the text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.errors import ArError, ErrorCode, NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.audit.memory import remember
from ar_domain.documents.strategy import (
    NamedText,
    ReadingPlan,
    choose,
    estimate_tokens,
    infer_task,
    normalise_strategy,
    normalise_task,
)
from ar_domain.files.logic import FileView, can_read_file
from ar_domain.knowledge.access import can_see
from ar_domain.runs.request import ask

if TYPE_CHECKING:
    import uuid

_CAP = 20


def bind_turn(
    store: Any,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    attachment_ids: list[uuid.UUID],
    file_ids: list[uuid.UUID],
    collection_ids: list[uuid.UUID],
    task: str,
    strategy: str,
    items: list[object],
    context_window: int | None,
) -> tuple[list[uuid.UUID], ReadingPlan]:
    """Resolve every id, choose a reading, and return the file ids to attach."""
    files = _unique(attachment_ids + file_ids)
    for file_id in files:
        _require_file(store, tenant_id, user_id, file_id)
    collections = _collections(store, tenant_id, user_id, collection_ids)
    named = _named(store, tenant_id, files)
    kind = normalise_task(task)
    if kind == "auto":
        kind = infer_task("", items=bool(items), documents=len(named))
    plan = choose(kind, normalise_strategy(strategy), named, context_window)
    del collections
    return files, plan


def remember_task(
    store: Any,
    run: dict[str, object],
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    file_ids: list[uuid.UUID],
    collection_ids: list[uuid.UUID],
    items: list[object],
    plan: ReadingPlan,
) -> None:
    """Store the turn's request and write ``document_task.started``."""
    ask(run, "task", plan.task)
    ask(run, "strategy", plan.strategy)
    ask(run, "items", [_item(item) for item in items])
    ask(run, "collection_ids", [str(item) for item in collection_ids])
    ask(run, "file_ids", [str(item) for item in file_ids])
    sizes = []
    files = getattr(store, "files", {})
    for file_id in file_ids:
        row = files.get(file_id) if isinstance(files, dict) else None
        size = int(row.get("size_bytes") or 0) if isinstance(row, dict) else 0
        sizes.append({"fileId": str(file_id), "bytes": size})
    remember(
        store,
        tenant_id=tenant_id,
        actor_id=user_id,
        action="document_task.started",
        target_type="run",
        target_id=run.get("id"),
        detail={
            "fileIds": [str(item) for item in file_ids],
            "collectionIds": [str(item) for item in collection_ids],
            "task": plan.task,
            "strategy": plan.strategy,
            "bytes": sizes,
        },
    )


def context_window_for(store: Any, tenant_id: uuid.UUID, run: dict[str, object]) -> int | None:
    """The registered window of the run's model. Missing stays missing."""
    from ar_domain.tools.agent_loop import _model_window  # noqa: PLC0415

    found = _model_window(store, run)
    if found is not None:
        return found
    del tenant_id
    return None


def _unique(ids: list[uuid.UUID]) -> list[uuid.UUID]:
    seen: set[uuid.UUID] = set()
    ordered: list[uuid.UUID] = []
    for file_id in ids:
        if file_id in seen:
            continue
        seen.add(file_id)
        ordered.append(file_id)
    return ordered


def _require_file(
    store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID, file_id: uuid.UUID
) -> dict[str, object]:
    files = getattr(store, "files", {})
    row = files.get(file_id) if isinstance(files, dict) else None
    if not isinstance(row, dict) or row.get("tenant_id") != tenant_id or row.get("deleted_at"):
        raise NotFoundError("file not found")
    view = FileView(
        tenant_id=str(row["tenant_id"]),
        owner_user_id=None if row.get("owner_user_id") is None else str(row.get("owner_user_id")),
        conversation_id=None
        if row.get("conversation_id") is None
        else str(row.get("conversation_id")),
        status=str(row.get("status") or ""),
    )
    owner = view.owner_user_id == str(user_id)
    shared = _file_in_readable_collection(store, tenant_id, user_id, row)
    if (
        not owner
        and not shared
        and not can_read_file(
            view,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            conversation_owner=_conversation_owner(store, tenant_id, user_id, row),
            read_all=False,
        )
    ):
        raise NotFoundError("file not found")
    if str(row.get("status") or "") != "ready":
        raise ArError(ErrorCode.INVALID_STATE, "file is not ready")
    library = _library_for(store, tenant_id, str(row.get("sha256") or ""))
    if isinstance(library, dict) and library.get("status") == "failed":
        code = str(library.get("error_code") or "text_not_extracted")
        raise ArError(ErrorCode.INVALID_STATE, f"The file could not be read ({code}).")
    return row


def _conversation_owner(
    store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID, file_row: dict[str, object]
) -> bool:
    conversation_id = file_row.get("conversation_id")
    conversations = getattr(store, "conversations", {})
    row = conversations.get(conversation_id) if isinstance(conversations, dict) else None
    if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
        return False
    return row.get("user_id") == user_id or row.get("created_by") == user_id


def _file_in_readable_collection(
    store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID, file_row: dict[str, object]
) -> bool:
    from ar_domain.knowledge.access import can_read_document  # noqa: PLC0415

    actor = Actor(tenant_id, user_id, frozenset({"chat:use", "knowledge:read"}))
    documents = getattr(store, "knowledge_documents", {})
    collections = getattr(store, "knowledge_collections", {})
    if not isinstance(documents, dict) or not isinstance(collections, dict):
        return False
    for document in documents.values():
        if not isinstance(document, dict) or document.get("raw_file_id") != file_row.get("id"):
            continue
        if document.get("status") == "deleted" or document.get("tenant_id") != tenant_id:
            continue
        collection = collections.get(document.get("collection_id"))
        if isinstance(collection, dict) and can_read_document(store, actor, document, collection):
            return True
    return False


def _library_for(store: Any, tenant_id: uuid.UUID, digest: str) -> dict[str, object] | None:
    if not digest:
        return None
    documents = getattr(store, "library_documents", {})
    if not isinstance(documents, dict):
        return None
    for row in documents.values():
        if (
            isinstance(row, dict)
            and row.get("tenant_id") == tenant_id
            and row.get("content_hash") == digest
        ):
            return row
    return None


def _collections(
    store: Any,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    collection_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    if len(collection_ids) > _CAP:
        raise ArError(ErrorCode.VALIDATION_FAILED, "name at most 20 collections")
    rows = getattr(store, "knowledge_collections", {})
    actor = Actor(tenant_id, user_id, frozenset({"chat:use", "knowledge:read"}))
    for collection_id in collection_ids:
        row = rows.get(collection_id) if isinstance(rows, dict) else None
        if not isinstance(row, dict) or not can_see(actor, row):
            raise NotFoundError("collection not found")
    return collection_ids


def _named(store: Any, tenant_id: uuid.UUID, file_ids: list[uuid.UUID]) -> list[NamedText]:
    named: list[NamedText] = []
    for file_id in file_ids:
        files = getattr(store, "files", {})
        meta = files.get(file_id) if isinstance(files, dict) else None
        digest = str(meta.get("sha256") or "") if isinstance(meta, dict) else ""
        library = _library_for(store, tenant_id, digest)
        passages = library.get("passages") if isinstance(library, dict) else []
        text = (
            "\n".join(str(item.get("text") or "") for item in passages if isinstance(item, dict))
            if isinstance(passages, list)
            else ""
        )
        headings = (
            {
                str(item.get("heading") or "")
                for item in passages
                if isinstance(item, dict) and item.get("heading")
            }
            if isinstance(passages, list)
            else set()
        )
        named.append(
            NamedText(
                file_id=str(file_id),
                document_id=str(library.get("id")) if isinstance(library, dict) else "",
                tokens=estimate_tokens(text),
                characters=len(text),
                headings=len(headings),
            )
        )
    return named


def _item(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "id": str(value.get("id") or ""),
            "text": str(value.get("text") or ""),
        }
    return {"id": "", "text": str(value)}
