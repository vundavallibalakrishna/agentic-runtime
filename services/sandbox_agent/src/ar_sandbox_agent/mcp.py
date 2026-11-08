"""Sandbox agent tools. The same path and egress rules as the dev computer.

The agent runs inside one sandbox container and exposes ``sandbox.*`` over ``/mcp``
to ``mcp-gateway`` only. It runs commands and reads and writes files in ``/workspace``;
nothing here reaches another sandbox. Spec: docs/03-specs/12-sandbox-manager.md §6.
"""

import base64
import binascii
import contextlib
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import Field

from ar_common.sandboxkit import (
    PathEscapeError,
    clean_env,
    confine,
    truncate_output,
    virtual_path,
)
from ar_contracts.api_model import ApiModel

router = APIRouter()

_MAX_WRITE = 10 * 1024 * 1024
_MAX_READ = 65536
_MAX_STDIN = 1024 * 1024


class ToolCall(ApiModel):
    name: str = ""
    arguments: dict[str, object] = Field(default_factory=dict)


def _root() -> Path:
    raw = os.environ.get("AR_SANDBOX_ROOT", "")
    base = Path(raw) if raw else Path("/tmp/ar-sandbox-agent")  # noqa: S108
    (base / "workspace").mkdir(parents=True, exist_ok=True)
    (base / "tmp").mkdir(parents=True, exist_ok=True)
    return base


def _auth(authorization: str | None) -> None:
    expected = os.environ.get("AR_SANDBOX_TOKEN", "")
    if not expected:
        return
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="token required")


@router.post("/mcp")
async def mcp(
    body: ToolCall, authorization: Annotated[str | None, Header()] = None
) -> dict[str, object]:
    _auth(authorization)
    return _call(body.name, body.arguments)


@router.get("/files")
async def list_files(
    path: Annotated[str, Query()] = "/workspace",
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _auth(authorization)
    return _call("list_files", {"path": path})


@router.put("/files/content")
async def write_file(
    request: Request,
    path: Annotated[str, Query()] = "/workspace",
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _auth(authorization)
    payload = (await request.body()).decode("utf-8", errors="replace")
    return _call("write_file", {"path": path, "content": payload})


@router.post("/admin/claim")
async def claim(authorization: Annotated[str | None, Header()] = None) -> dict[str, str]:
    _auth(authorization)
    return {"status": "ready", "root": str(_root())}


@router.post("/admin/snapshot")
async def snapshot(authorization: Annotated[str | None, Header()] = None) -> dict[str, int]:
    _auth(authorization)
    root = _root() / "workspace"
    total = 0
    if root.exists():
        total = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
    return {"bytes": total}


@router.post("/admin/restore")
async def restore(authorization: Annotated[str | None, Header()] = None) -> dict[str, str]:
    _auth(authorization)
    _root()
    return {"status": "ready"}


def _call(name: str, arguments: dict[str, object]) -> dict[str, object]:
    root = _root()
    bare = name.split(".", 1)[-1]  # accept "sandbox.exec" or "exec"
    try:
        if bare in {"read_file", "list_files", "write_file"}:
            return _with_usage(_files(root, bare, arguments))
        if bare == "exec":
            return _with_usage(_exec(root, arguments))
    except PathEscapeError as exc:
        return {"text": str(exc), "is_error": True, "code": "validation_failed"}
    return {"text": f"unknown tool {name}", "is_error": True, "code": "unknown_tool"}


def _exec(root: Path, arguments: dict[str, object]) -> dict[str, object]:
    """Run one bash command in the workspace and report its output and new files."""
    command = str(arguments.get("command") or "")
    workspace = root / "workspace"
    if not command.strip():
        return {
            "text": "",
            "structured": {
                "exit_code": 0,
                "stdout": "",
                "stderr": "",
                "truncated": False,
                "duration_ms": 0,
                "new_files": [],
            },
            "is_error": False,
        }
    ceiling = _as_int(os.environ.get("AR_SANDBOX_EXEC_TIMEOUT_S"), 120)
    timeout = max(1, min(_as_int(arguments.get("timeout_s"), ceiling), ceiling))
    cwd = confine(root, str(arguments.get("cwd") or "/workspace"))
    raw_env = arguments.get("env")
    supplied = (
        {str(key): str(value) for key, value in raw_env.items()}
        if isinstance(raw_env, dict)
        else {}
    )
    env = clean_env(supplied)
    env["SANDBOX_WORKSPACE"] = str(workspace)
    env.setdefault("PATH", os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"))
    env.setdefault("HOME", str(root))
    stdin = str(arguments.get("stdin") or "")[:_MAX_STDIN]
    before = _stamp(workspace)
    started = time.monotonic()
    proc = subprocess.Popen(  # noqa: S603
        ["/bin/bash", "-lc", command],
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    try:
        out, err = proc.communicate(stdin.encode(), timeout=timeout)
        code = proc.returncode or 0
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError, ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        code, timed_out = 124, True
    duration_ms = int((time.monotonic() - started) * 1000)
    stdout, stderr, truncated = truncate_output(out or b"", err or b"")
    if timed_out:
        stderr = f"{stderr.rstrip()}\nthe command timed out".lstrip()
    return {
        "text": stdout or stderr or "done",
        "structured": {
            "exit_code": code,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": truncated,
            "duration_ms": duration_ms,
            "new_files": _new_files(workspace, before),
        },
        "is_error": code != 0,
    }


def _files(root: Path, name: str, arguments: dict[str, object]) -> dict[str, object]:
    target = confine(root, str(arguments.get("path") or "/workspace"))
    if name == "list_files":
        return _list(root, target, arguments)
    if name == "write_file":
        return _write(target, arguments)
    offset = max(0, _as_int(arguments.get("offset"), 0))
    limit = max(1, min(_as_int(arguments.get("limit"), _MAX_READ), _MAX_READ))
    if not target.is_file():
        return {"text": "file was not found", "is_error": True, "code": "not_found"}
    data = target.read_bytes()
    window = data[offset : offset + limit]
    if str(arguments.get("encoding") or "utf8") == "base64":
        content = base64.b64encode(window).decode("ascii")
    else:
        content = window.decode("utf-8", errors="replace")
    return {
        "text": content,
        "structured": {
            "content": content,
            "size_bytes": len(data),
            "eof": offset + limit >= len(data),
        },
        "is_error": False,
    }


def _write(target: Path, arguments: dict[str, object]) -> dict[str, object]:
    content = str(arguments.get("content") or "")
    if str(arguments.get("encoding") or "utf8") == "base64":
        try:
            raw = base64.b64decode(content, validate=True)
        except ValueError, binascii.Error:
            return {
                "text": "content is not valid base64",
                "is_error": True,
                "code": "validation_failed",
            }
    else:
        raw = content.encode("utf-8")
    if len(raw) > _MAX_WRITE:
        return {"text": "the file is over 10 MiB", "is_error": True, "code": "validation_failed"}
    target.parent.mkdir(parents=True, exist_ok=True)
    if arguments.get("append") is True and target.is_file():
        raw = target.read_bytes() + raw
    target.write_bytes(raw)
    return {
        "text": f"wrote {len(raw)}",
        "structured": {"bytes_written": len(raw)},
        "is_error": False,
    }


def _list(root: Path, target: Path, arguments: dict[str, object]) -> dict[str, object]:
    if not target.exists():
        return {"text": "", "structured": {"entries": []}, "is_error": False}
    cap = max(1, min(_as_int(arguments.get("max_entries"), 1000), 1000))
    walker = target.rglob("*") if arguments.get("recursive") is True else target.iterdir()
    entries = [virtual_path(root, path) for path in sorted(walker) if not path.name.startswith("_")]
    entries = entries[:cap]
    return {"text": "\n".join(entries), "structured": {"entries": entries}, "is_error": False}


def _stamp(workspace: Path) -> dict[str, int]:
    found: dict[str, int] = {}
    if workspace.is_dir():
        for path in workspace.rglob("*"):
            if path.is_file():
                found[str(path)] = path.stat().st_mtime_ns
    return found


def _new_files(workspace: Path, before: dict[str, int]) -> list[str]:
    found: list[str] = []
    if not workspace.is_dir():
        return found
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.name.startswith("_"):
            continue
        if before.get(str(path)) != path.stat().st_mtime_ns:
            found.append(virtual_path(workspace.parent, path))
    return found[:20]


def _with_usage(result: dict[str, object]) -> dict[str, object]:
    """Attach the cumulative CPU usage the gateway meters deltas from (spec 12 §6)."""
    result["_meta"] = {"io.agentic-runtime/usage": {"cpu_seconds_total": _cpu_seconds()}}
    return result


def _cpu_seconds() -> float:
    try:
        for line in Path("/sys/fs/cgroup/cpu.stat").read_text(encoding="utf-8").splitlines():
            if line.startswith("usage_usec"):
                return int(line.split()[1]) / 1_000_000
    except OSError, ValueError:
        return 0.0
    return 0.0


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, (float, str)):
        try:
            return int(value)
        except TypeError, ValueError:
            return default
    return default
