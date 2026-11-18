"""Deterministic Office zip packages. Dates are fixed so smoke files stay stable."""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

PRODUCER = "Cura Works"
_WHEN = (2026, 1, 1, 0, 0, 0)


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def pack(parts: Mapping[str, str | bytes]) -> bytes:
    """Store each part uncompressed with a fixed timestamp. Text is written as UTF-8."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as book:
        for name in sorted(parts):
            info = zipfile.ZipInfo(filename=name, date_time=_WHEN)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            info.create_system = 0
            part = parts[name]
            book.writestr(info, part.encode("utf-8") if isinstance(part, str) else part)
    return buffer.getvalue()
