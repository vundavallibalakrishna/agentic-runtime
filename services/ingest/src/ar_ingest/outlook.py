"""Read an Outlook .msg file. This module is imported only by the ingest worker."""

from __future__ import annotations

import tempfile
from pathlib import Path


def parse_outlook(data: bytes) -> dict[str, object]:
    """Headers, body and attachments. Nested messages are attachments, read later."""
    import extract_msg  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "message.msg"
        path.write_bytes(data)
        message = extract_msg.Message(str(path))
        try:
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
            attachments: list[dict[str, object]] = []
            for item in message.attachments:
                name = str(
                    getattr(item, "longFilename", None)
                    or getattr(item, "shortFilename", None)
                    or "attachment"
                )
                payload = getattr(item, "data", None)
                if isinstance(payload, bytes) and payload:
                    attachments.append({"filename": name, "data": payload})
        finally:
            message.close()
    return {"text": text, "headers": headers, "attachments": attachments}
