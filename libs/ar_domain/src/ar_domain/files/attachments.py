"""The files a person attached to a conversation. Spec: docs/03-specs/13-files-artifacts.md §4.

One place decides which files a turn has and where each sits in the working folder, so
the prompt, the run's folder and the sandbox all name a file the same way. A file stays
with its conversation: a later turn still has what an earlier message attached.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from ar_common.sandboxkit import sanitise_name

if TYPE_CHECKING:
    from typing import Any

INPUTS = "inputs"
_KIB = 1024
# How much of an attached document a prompt shows before the model reads the rest with a tool.
_EXCERPT = 1500


@dataclass(frozen=True, slots=True)
class Attachment:
    """One attached file and its place in the working folder."""

    file_id: uuid.UUID
    message_id: uuid.UUID | None
    name: str
    mime_type: str
    size_bytes: int
    path: str
    document_id: uuid.UUID | None = None
    excerpt: str = ""

    def line(self) -> str:
        """How the prompt names the file: what it is, its id and its path."""
        document = f" documentId={self.document_id}" if self.document_id else ""
        text = (
            f"[file: {self.name} ({self.mime_type}, {_size(self.size_bytes)}) "
            f"id={self.file_id}{document} path={self.path}]"
        )
        if self.excerpt:
            return f"{text}\n{self.excerpt}"
        return text


def conversation_attachments(store: Any, conversation_id: object) -> list[Attachment]:
    """Every file attached in the conversation, oldest first, each with its own path.

    Two files with the same name get different paths: the later one carries the start
    of its id. A file attached twice is listed once, where it was first attached.
    """
    if not isinstance(conversation_id, uuid.UUID):
        return []
    messages = [
        row
        for row in list(getattr(store, "messages", {}).values())
        if isinstance(row, dict)
        and row.get("conversation_id") == conversation_id
        and row.get("role") == "user"
        and row.get("is_active_branch") is not False
    ]
    messages.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
    found: list[Attachment] = []
    taken: set[str] = set()
    seen: set[uuid.UUID] = set()
    files = getattr(store, "files", {})
    for message in messages:
        for file_id in _file_ids(message):
            meta = files.get(file_id)
            if file_id in seen or not isinstance(meta, dict) or meta.get("deleted_at"):
                continue
            if meta.get("tenant_id") != message.get("tenant_id"):
                continue
            seen.add(file_id)
            path = _path(str(meta.get("name") or "upload"), file_id, taken)
            taken.add(path)
            message_id = message.get("id")
            document_id, excerpt = _library_excerpt(store, meta)
            found.append(
                Attachment(
                    file_id=file_id,
                    message_id=message_id if isinstance(message_id, uuid.UUID) else None,
                    name=str(meta.get("name") or "upload"),
                    mime_type=str(meta.get("mime_type") or "application/octet-stream"),
                    size_bytes=int(meta.get("size_bytes") or 0),
                    path=path,
                    document_id=document_id,
                    excerpt=excerpt,
                )
            )
    return found


def attachment_lines(attachments: list[Attachment]) -> str:
    """The lines a prompt shows for these files. Empty when there are none."""
    return "\n".join(item.line() for item in attachments)


def _file_ids(message: dict[str, object]) -> list[uuid.UUID]:
    """The ids in the message's file parts, in the order they were attached."""
    content = message.get("content")
    ids: list[uuid.UUID] = []
    for part in content if isinstance(content, list) else []:
        if not isinstance(part, dict) or part.get("type") != "file":
            continue
        try:
            ids.append(uuid.UUID(str(part.get("file_id"))))
        except ValueError:
            continue
    return ids


def _path(name: str, file_id: uuid.UUID, taken: set[str]) -> str:
    clean = sanitise_name(name)
    path = f"{INPUTS}/{clean}"
    if path not in taken:
        return path
    pure = PurePosixPath(clean)
    return f"{INPUTS}/{pure.stem}-{file_id.hex[:8]}{pure.suffix}"


def _library_excerpt(store: Any, meta: dict[str, object]) -> tuple[uuid.UUID | None, str]:
    """The library document for these bytes, and a short passage the turn can read."""
    digest = str(meta.get("sha256") or "")
    documents = getattr(store, "library_documents", None)
    if not digest or not isinstance(documents, dict):
        return None, ""
    for row in documents.values():
        if not isinstance(row, dict):
            continue
        if row.get("tenant_id") != meta.get("tenant_id") or row.get("content_hash") != digest:
            continue
        raw = row.get("id")
        document_id = raw if isinstance(raw, uuid.UUID) else None
        return document_id, _excerpt(row.get("passages"))
    return None, ""


def _excerpt(passages: object) -> str:
    """The first passages of a document, each after its anchor, whole passages only.

    The anchor is what the model cites, so a passage is never shown without it.
    """
    from ar_domain.documents.cited import passage_line  # noqa: PLC0415

    lines: list[str] = []
    used = 0
    for item in passages if isinstance(passages, list) else []:
        if not isinstance(item, dict) or not item.get("text") or not item.get("anchor"):
            continue
        line = passage_line(item)
        if lines and used + len(line) > _EXCERPT:
            break
        lines.append(line[:_EXCERPT])
        used += len(line) + 1
    return "\n".join(lines)


def _size(size: int) -> str:
    if size < _KIB:
        return f"{size} B"
    if size < _KIB * _KIB:
        return f"{size / _KIB:.1f} kB"
    return f"{size / (_KIB * _KIB):.1f} MB"
