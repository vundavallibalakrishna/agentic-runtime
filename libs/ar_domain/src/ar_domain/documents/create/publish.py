"""Save a created file on the run workspace and as a downloadable artifact."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.sandboxkit import PathEscapeError, confine, virtual_path
from ar_domain.documents.create.render import render
from ar_domain.documents.create.spec import MEDIA, CreateError, max_file_bytes, parse

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
    kept = keep_output(
        store, arguments, filename=spec.filename, data=data, media=MEDIA[spec.format]
    )
    if kept is None:
        return _error("validation_failed", "The file name is not allowed.")
    saved, shown = kept
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


def keep_output(
    store: Any, arguments: dict[str, object], *, filename: str, data: bytes, media: str
) -> tuple[dict[str, str], str] | None:
    """Put a file a tool wrote under /workspace/outputs and keep it for download.

    Returns the stored file and the path shown to the model, or ``None`` when the name
    would leave the run's folder.
    """
    from ar_domain.tools.general import _prepare, _store_file  # noqa: PLC0415

    root = _prepare(store, arguments)
    try:
        target = confine(root, f"/workspace/outputs/{filename}")
    except PathEscapeError:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    if not isinstance(getattr(store, "files", None), dict):
        store.files = {}
    if not isinstance(getattr(store, "blobs", None), dict):
        store.blobs = {}
    saved = _store_file(store, arguments, name=filename, data=data)
    row = store.files.get(uuid.UUID(saved["file_id"]))
    if isinstance(row, dict):
        row["mime_type"] = media
    return saved, virtual_path(root, target)


def _cap(store: Any, arguments: dict[str, object]) -> int:
    if not isinstance(getattr(store, "versions", None), dict):
        return max_file_bytes()
    from ar_domain.tools.general import _limits  # noqa: PLC0415

    limit = _limits(store, arguments, "write_file")["max_file_bytes"]
    if isinstance(limit, int) and not isinstance(limit, bool):
        return limit
    return max_file_bytes()


def _ok(text: str, presentation: dict[str, object]) -> dict[str, object]:
    return {"text": text, "structured": {"presentation": presentation}, "is_error": False}


def _error(code: str, message: str) -> dict[str, object]:
    return {
        "text": message,
        "structured": {"presentation": {"kind": "error", "message": message}, "code": code},
        "is_error": True,
        "code": code,
    }
