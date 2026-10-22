"""Sandbox agent tools. The same path and egress rules as the dev computer."""

import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import Field

from ar_common.sandboxkit import PathEscapeError, confine, truncate_output, virtual_path
from ar_contracts.api_model import ApiModel

router = APIRouter()


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
    try:
        if name in {"read_file", "list_files", "write_file"}:
            return _files(root, name, arguments)
        if name == "exec":
            return {"text": "exec runs in the computer image", "is_error": False, "structured": {}}
    except PathEscapeError as exc:
        return {"text": str(exc), "is_error": True, "code": "validation_failed"}
    return {"text": f"unknown tool {name}", "is_error": True, "code": "unknown_tool"}


def _files(root: Path, name: str, arguments: dict[str, object]) -> dict[str, object]:
    target = confine(root, str(arguments.get("path") or "/workspace"))
    if name == "list_files":
        entries = []
        if target.exists():
            entries = [virtual_path(root, path) for path in target.iterdir()]
        return {"text": "\n".join(entries), "structured": {"entries": entries}, "is_error": False}
    if name == "write_file":
        content = str(arguments.get("content") or "")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"text": f"wrote {len(content)}", "is_error": False, "structured": {}}
    if not target.is_file():
        return {"text": "file was not found", "is_error": True, "code": "not_found"}
    data = target.read_bytes()
    text, _, truncated = truncate_output(data, b"")
    return {"text": text, "structured": {"truncated": truncated}, "is_error": False}
