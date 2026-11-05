"""Deterministic Office zip packages. Dates are fixed so smoke files stay stable."""

from __future__ import annotations

import io
import zipfile

_WHEN = (2026, 1, 1, 0, 0, 0)


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def pack(parts: dict[str, str]) -> bytes:
    """Store each part uncompressed with a fixed timestamp."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as book:
        for name in sorted(parts):
            info = zipfile.ZipInfo(filename=name, date_time=_WHEN)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            info.create_system = 0
            book.writestr(info, parts[name].encode("utf-8"))
    return buffer.getvalue()
