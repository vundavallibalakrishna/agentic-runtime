"""Save a created file on the run workspace and as a downloadable artifact."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.sandboxkit import PathEscapeError, confine, virtual_path
from ar_domain.documents.create.render import render
from ar_domain.documents.create.spec import MAX_FILE_BYTES, MEDIA, CreateError, parse

if TYPE_CHECKING:
    from typing import Any


def publish(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    """Write the file under /workspace/outputs and return the chat download card."""
    try:
        spec = parse(arguments)
        data = render(spec)
    except CreateError as exc:
        return _error("validation_failed", str(exc))
    cap = _cap(store, arguments)
    if len(data) > cap:
        return _error("file_too_large", "The document is over the file size limit. Shorten it.")
    from ar_domain.tools.general import _prepare, _store_file  # noqa: PLC0415

    root = _prepare(store, arguments)
    try:
        target = confine(root, f"/workspace/outputs/{spec.filename}")
    except PathEscapeError:
        return _error("validation_failed", "The file name is not allowed.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    if not isinstance(getattr(store, "files", None), dict):
        store.files = {}
    if not isinstance(getattr(store, "blobs", None), dict):
        store.blobs = {}
    saved = _store_file(store, arguments, name=spec.filename, data=data)
    file_id = uuid.UUID(saved["file_id"])
    row = store.files.get(file_id)
    if isinstance(row, dict):
        row["mime_type"] = MEDIA[spec.format]
    shown = virtual_path(root, target)
    text = f"Wrote {shown} ({len(data)} bytes)."
    return _ok(
        text,
        {
            "kind": "file",
            "format": spec.format,
            "path": shown,
            "title": spec.title,
            "template": spec.template,
            "files": [saved],
        },
    )


def _cap(store: Any, arguments: dict[str, object]) -> int:
    if not isinstance(getattr(store, "versions", None), dict):
        return MAX_FILE_BYTES
    from ar_domain.tools.general import _limits  # noqa: PLC0415

    limit = _limits(store, arguments, "write_file")["max_file_bytes"]
    if isinstance(limit, int) and not isinstance(limit, bool):
        return limit
    return MAX_FILE_BYTES


def _ok(text: str, presentation: dict[str, object]) -> dict[str, object]:
    return {"text": text, "structured": {"presentation": presentation}, "is_error": False}


def _error(code: str, message: str) -> dict[str, object]:
    return {
        "text": message,
        "structured": {"presentation": {"kind": "error", "message": message}, "code": code},
        "is_error": True,
        "code": code,
    }
