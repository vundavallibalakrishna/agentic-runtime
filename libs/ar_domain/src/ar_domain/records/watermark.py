"""Guest watermarks. The original bytes are never returned. Spec: spec 21 §4.1."""

import hashlib
import struct


class WatermarkError(Exception):
    """The rendition could not be built. Callers must not send the original."""


def watermark(data: bytes, media_type: str, label: str) -> bytes:
    """Return bytes that contain the label and differ from the original."""
    if not label:
        raise WatermarkError("missing label")
    kind = media_type.lower()
    if kind == "application/pdf":
        return _pdf(data, label)
    if kind == "image/png":
        return _png(data, label)
    if kind in {"image/jpeg", "image/jpg"}:
        return _jpeg(data, label)
    raise WatermarkError("unsupported")


def _pdf(data: bytes, label: str) -> bytes:
    note = f"\n% watermark {label}\n".encode()
    if b"%%EOF" in data:
        return data.replace(b"%%EOF", note + b"%%EOF", 1)
    return data + note


def _png(data: bytes, label: str) -> bytes:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise WatermarkError("not a png")
    chunk = _png_text(label)
    marker = b"IEND"
    index = data.rfind(marker)
    if index < 4:
        raise WatermarkError("png has no end")
    start = index - 4
    return data[:start] + chunk + data[start:]


def _png_text(label: str) -> bytes:
    payload = b"Comment\x00" + label.encode()
    header = struct.pack(">I", len(payload)) + b"tEXt" + payload
    checksum = struct.pack(">I", _crc(b"tEXt" + payload))
    return header + checksum


def _crc(payload: bytes) -> int:
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") & 0xFFFFFFFF


def _jpeg(data: bytes, label: str) -> bytes:
    if not data.startswith(b"\xff\xd8"):
        raise WatermarkError("not a jpeg")
    comment = b"\xff\xfe" + struct.pack(">H", len(label.encode()) + 2) + label.encode()
    return data[:2] + comment + data[2:]
