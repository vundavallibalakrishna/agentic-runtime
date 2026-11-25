"""Read an Outlook .msg file. This module is imported only by the ingest worker."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

_DEFAULT_MAX_ATTACHMENTS = 32
_DEFAULT_MAX_BYTES = 25_000_000


def parse_outlook(
    data: bytes,
    *,
    max_attachments: int | None = None,
    max_bytes: int | None = None,
) -> dict[str, object]:
    """Headers, body and attachments, including a message nested inside another."""
    import extract_msg  # noqa: PLC0415

    limits = _limits(max_attachments, max_bytes)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "message.msg"
        path.write_bytes(data)
        message = extract_msg.Message(str(path))
        try:
            return _read_message(message, parent="", limits=limits, state={"count": 0, "bytes": 0})
        finally:
            message.close()


def _limits(max_attachments: int | None, max_bytes: int | None) -> tuple[int, int]:
    count = _DEFAULT_MAX_ATTACHMENTS if max_attachments is None else max_attachments
    size = _DEFAULT_MAX_BYTES if max_bytes is None else max_bytes
    return max(1, count), max(1, size)


def _read_message(
    message: Any, *, parent: str, limits: tuple[int, int], state: dict[str, int]
) -> dict[str, object]:
    headers = {
        "subject": str(message.subject or ""),
        "from": str(message.sender or ""),
        "to": str(message.to or ""),
        "date": str(message.date or ""),
    }
    lines = [f"{name}: {value}" for name, value in headers.items() if value]
    body = str(message.body or "")
    text = "\n".join(lines)
    if body.strip():
        text = f"{text}\n\n{body}" if text else body
    attachments = _attachments(
        message, parent=headers["subject"] or parent, limits=limits, state=state
    )
    return {"text": text, "headers": headers, "attachments": attachments, "parent": parent}


def _attachments(
    message: Any, *, parent: str, limits: tuple[int, int], state: dict[str, int]
) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for item in message.attachments:
        state["count"] += 1
        if state["count"] > limits[0]:
            raise ValueError(f"the message has more than {limits[0]} attachments")
        name = str(
            getattr(item, "longFilename", None)
            or getattr(item, "shortFilename", None)
            or "attachment"
        )
        kind = str(getattr(getattr(item, "type", None), "name", "") or "")
        nested = getattr(item, "data", None)
        if kind == "MSG" and nested is not None and not isinstance(nested, bytes):
            found.append(
                {
                    "filename": name or "message.msg",
                    "kind": "message",
                    "parent": parent,
                    "message": _read_message(nested, parent=parent, limits=limits, state=state),
                }
            )
            continue
        payload = nested if isinstance(nested, bytes) else b""
        state["bytes"] += len(payload)
        if state["bytes"] > limits[1]:
            raise ValueError(f"the message attachments are over {limits[1]} bytes")
        if payload:
            found.append({"filename": name, "kind": "file", "parent": parent, "data": payload})
    return found
