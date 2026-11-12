"""Run a script from a run's working folder inside the conversation's computer.

The general tools keep one working folder per run. Where code may not run on the host,
``general.code`` and ``general.shell`` run it in the computer: the folder is copied in,
the script runs there, and the files it wrote are copied back, so every other tool finds
them in the folder as before.
"""

from __future__ import annotations

import base64
import binascii
import shlex
from typing import TYPE_CHECKING, Any

from ar_common.isolate import IsolatedRun
from ar_common.offload import blocking
from ar_common.sandboxkit import PathEscapeError, confine
from ar_domain.sandboxes.runtime import call_computer, computer_for_call, read_computer_file

if TYPE_CHECKING:
    from pathlib import Path

# The computer's agent takes at most this much in one write.
_MAX_PUSH = 10 * 1024 * 1024


def runs_in_computer(store: Any) -> bool:
    """Whether this process has a place to start computers: a launcher or the manager."""
    return getattr(store, "sandbox_launcher", None) is not None


def run_in_computer(
    store: Any,
    arguments: dict[str, object],
    root: Path,
    command: list[str],
    *,
    timeout: int,
) -> IsolatedRun | dict[str, object]:
    """Run ``command`` in the computer's working folder, which holds the run's folder.

    A path in ``command`` is relative to that folder.

    Returns the finished run, or the tool error when the computer could not be reached.
    """
    found = computer_for_call(store, arguments)
    sandbox = found.get("sandbox")
    if found.get("is_error") or not isinstance(sandbox, dict):
        return found if found.get("is_error") else _unavailable("the computer is not ready")
    if not sandbox.get("endpoint_url"):
        return _unavailable("the computer is not ready")
    workspace = root / "workspace"
    refused = blocking(_push, sandbox, workspace)
    if refused is not None:
        return refused
    line = " ".join(shlex.quote(part) for part in command)
    body = call_computer(
        sandbox,
        "exec",
        {"command": line, "cwd": "/workspace", "timeout_s": timeout},
        timeout=float(timeout + 10),
    )
    raw = body.get("structured")
    structured = raw if isinstance(raw, dict) else {}
    if "exit_code" not in structured:
        return _unavailable(str(body.get("text") or "the computer did not answer"))
    written = structured.get("new_files")
    blocking(_pull, sandbox, root, written if isinstance(written, list) else [])
    return IsolatedRun(
        exit_code=int(structured.get("exit_code") or 0),
        stdout=str(structured.get("stdout") or ""),
        stderr=str(structured.get("stderr") or ""),
        truncated=bool(structured.get("truncated")),
        # The computer has a real /workspace, as a private root on the host does.
        mode="namespace",
    )


def _push(sandbox: dict[str, object], workspace: Path) -> dict[str, object] | None:
    """Copy the folder into the computer. A file the agent cannot take stays behind."""
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) > _MAX_PUSH:
            continue
        sent = call_computer(
            sandbox,
            "write_file",
            {
                "path": f"/workspace/{path.relative_to(workspace).as_posix()}",
                "content": base64.b64encode(data).decode("ascii"),
                "encoding": "base64",
            },
        )
        if sent.get("is_error"):
            return _unavailable(str(sent.get("text") or "the computer did not take a file"))
    return None


def _pull(sandbox: dict[str, object], root: Path, written: list[object]) -> None:
    """Copy what the command wrote back into the run's folder."""
    for raw in written:
        data = read_computer_file(sandbox, str(raw))
        if data is None:
            continue
        try:
            target = confine(root, str(raw))
        except PathEscapeError, binascii.Error:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def _unavailable(message: str) -> dict[str, object]:
    return {
        "text": message,
        "structured": {},
        "is_error": True,
        "code": "sandbox_unavailable",
    }
