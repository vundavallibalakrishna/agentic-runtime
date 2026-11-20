"""Talk to clamd. A scanner that does not answer is an error, not a clean file."""

from __future__ import annotations

import socket
import struct

_CHUNK = 65536


def instream(data: bytes, address: str, *, timeout_s: float) -> str:
    """``clean``, ``infected`` or ``error``.

    ``error`` is a socket that is missing, refused or unreadable. The caller
    rejects the upload.
    """
    endpoint = address.strip()
    if not endpoint:
        return "error"
    try:
        with _connect(endpoint, timeout_s) as sock:
            sock.sendall(b"zINSTREAM\0")
            view = memoryview(data)
            for start in range(0, len(view), _CHUNK):
                piece = view[start : start + _CHUNK]
                sock.sendall(struct.pack("!I", len(piece)))
                sock.sendall(piece)
            sock.sendall(struct.pack("!I", 0))
            reply = _read(sock)
    except OSError:
        return "error"
    text = reply.decode("utf-8", errors="replace").strip("\x00\n ")
    if text.endswith("OK"):
        return "clean"
    if "FOUND" in text:
        return "infected"
    return "error"


def _connect(address: str, timeout_s: float) -> socket.socket:
    if address.startswith("/"):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout_s)
        sock.connect(address)
        return sock
    host, separator, port = address.rpartition(":")
    if not separator or not port.isdigit():
        raise OSError("clamav address is not host:port")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    sock.connect((host, int(port)))
    return sock


def _read(sock: socket.socket) -> bytes:
    parts: list[bytes] = []
    while True:
        piece = sock.recv(4096)
        if not piece:
            break
        parts.append(piece)
        if b"\x00" in piece or b"\n" in piece:
            break
    return b"".join(parts)
