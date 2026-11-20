"""Copy a computer's working folder out before its container stops, and back in after.

The agent inside the container has no call that hands over the folder, so this uses the
calls it does have: a command packs ``/workspace`` into pieces small enough to read, the
pieces are read one by one, and on the way back they are written and unpacked. What
comes back is everything under ``/workspace``: files, folders, links and permissions.
Nothing outside it survives: not the home folder, not ``/tmp``, not installed packages,
not a running process, not the browser's pages.
Spec: docs/03-specs/12-sandbox-manager.md §5.
"""

from __future__ import annotations

import base64
import binascii

from ar_domain.sandboxes.runtime import call_computer

# Where the pieces wait, inside the working folder. It is never part of the snapshot.
# Commands name it relative to the working folder; the agent's file calls name it in full.
_STAGE = ".ar-suspend"
_STAGE_PATH = f"/workspace/{_STAGE}"
# One piece is one read: the agent returns at most this much of a file per call.
_READ_PIECE = 65536
# One piece on the way back. The agent takes a request body of about a mebibyte.
_WRITE_PIECE = 512 * 1024
_COMMAND_S = 120

MIME = "application/gzip"


class SnapshotError(ValueError):
    """The working folder could not be copied out or back. The computer is left as it was."""


def take(sandbox: dict[str, object], *, max_bytes: int) -> bytes:
    """The computer's working folder as one compressed archive.

    Raises ``SnapshotError`` when the folder cannot be packed or is larger than
    ``max_bytes`` packed. The pieces are removed from the computer either way.
    """
    packed = _run(
        sandbox,
        f"set -o pipefail; rm -rf {_STAGE} && mkdir -p {_STAGE} && "
        f"tar -czf - --exclude=./{_STAGE} . | "
        f"split -d -a 6 -b {_READ_PIECE} - {_STAGE}/part. && ls {_STAGE} | wc -l",
    )
    try:
        if packed is None:
            raise SnapshotError("the working folder could not be packed")
        count = packed.strip()
        if not count.isdigit():
            raise SnapshotError("the working folder could not be packed")
        pieces = int(count)
        if pieces * _READ_PIECE > max_bytes + _READ_PIECE:
            raise SnapshotError("the working folder is larger than a snapshot may be")
        data = bytearray()
        for index in range(pieces):
            data.extend(_read_piece(sandbox, f"{_STAGE_PATH}/part.{index:06d}"))
        return bytes(data)
    finally:
        _run(sandbox, f"rm -rf {_STAGE}")


def put(sandbox: dict[str, object], blob: bytes) -> None:
    """Unpack an archive from ``take`` into the computer's working folder.

    Raises ``SnapshotError`` when a piece is refused or the archive does not unpack.
    """
    if not blob:
        return
    if _run(sandbox, f"rm -rf {_STAGE} && mkdir -p {_STAGE} && echo ok") is None:
        raise SnapshotError("the computer did not take the snapshot")
    for index, start in enumerate(range(0, len(blob), _WRITE_PIECE)):
        sent = call_computer(
            sandbox,
            "write_file",
            {
                "path": f"{_STAGE_PATH}/part.{index:06d}",
                "content": base64.b64encode(blob[start : start + _WRITE_PIECE]).decode("ascii"),
                "encoding": "base64",
            },
        )
        if sent.get("is_error"):
            raise SnapshotError("the computer did not take the snapshot")
    unpacked = _run(
        sandbox,
        f"set -o pipefail; cat {_STAGE}/part.* | tar -xzf - && rm -rf {_STAGE} && echo ok",
    )
    if unpacked is None:
        raise SnapshotError("the snapshot did not unpack")


def _run(sandbox: dict[str, object], command: str) -> str | None:
    """Run one command in the computer. Its output, or ``None`` when it did not succeed."""
    body = call_computer(
        sandbox,
        "exec",
        {"command": command, "cwd": "/workspace", "timeout_s": _COMMAND_S},
        timeout=float(_COMMAND_S + 10),
    )
    raw = body.get("structured")
    structured = raw if isinstance(raw, dict) else {}
    if structured.get("exit_code") != 0:
        return None
    return str(structured.get("stdout") or "")


def _read_piece(sandbox: dict[str, object], path: str) -> bytes:
    read = call_computer(
        sandbox,
        "read_file",
        {"path": path, "encoding": "base64", "offset": 0, "limit": _READ_PIECE},
    )
    raw = read.get("structured")
    content = raw.get("content") if isinstance(raw, dict) else None
    if read.get("is_error") or not isinstance(content, str):
        raise SnapshotError("a piece of the working folder could not be read")
    try:
        return base64.b64decode(content)
    except (ValueError, binascii.Error) as exc:
        raise SnapshotError("a piece of the working folder could not be read") from exc
