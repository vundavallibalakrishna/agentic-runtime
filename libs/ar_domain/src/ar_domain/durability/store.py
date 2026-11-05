"""Remember file bytes and workspace files outside the process temp directory.

Bodies at or under the cap are copied onto the process store so a flush can
write them. Larger bodies stay on the temp directory only.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember

if TYPE_CHECKING:
    from collections.abc import Mapping

_MAX_BLOB = 8 * 1024 * 1024
_MAX_WORKSPACE_FILE = 2 * 1024 * 1024
_MAX_WORKSPACE = 8 * 1024 * 1024


def workspace_root(run_id: uuid.UUID) -> Path:
    """Host directory for one run. The same path ``general`` tools already use."""
    base = Path(os.environ.get("TMPDIR", tempfile.gettempdir()))
    return base / "ar-run-workspaces" / str(run_id)


def remember_blob(store: Any, row: Mapping[str, object], data: bytes) -> None:
    """Keep a copy of a file that fits the durable cap."""
    if len(data) > _MAX_BLOB:
        return
    file_id = row.get("id")
    tenant_id = row.get("tenant_id")
    if not isinstance(file_id, uuid.UUID) or not isinstance(tenant_id, uuid.UUID):
        return
    book = _book(store, "file_blobs")
    book[file_id] = {
        "id": file_id,
        "tenant_id": tenant_id,
        "owner_user_id": row.get("owner_user_id"),
        "conversation_id": row.get("conversation_id"),
        "run_id": row.get("run_id"),
        "name": str(row.get("name") or "file"),
        "mime_type": str(row.get("mime_type") or "application/octet-stream"),
        "sha256": str(row.get("sha256") or hashlib.sha256(data).hexdigest()),
        "size_bytes": len(data),
        "kind": str(row.get("kind") or "upload"),
        "body": data,
        "created_at": row.get("created_at") or utcnow(),
        "updated_at": utcnow(),
    }


def read_blob(store: Any, file_id: uuid.UUID) -> bytes | None:
    """Return bytes from the cache, the durable copy, or Postgres."""
    blobs = getattr(store, "blobs", None)
    if isinstance(blobs, dict):
        found = blobs.get(file_id)
        if isinstance(found, (bytes, bytearray, memoryview)):
            return bytes(found)
    row = _row(store, "file_blobs", file_id)
    cached = _body(row)
    if cached is not None:
        if isinstance(blobs, dict):
            blobs[file_id] = cached
        return cached
    loaded = _load_blob(store, file_id)
    if loaded is None:
        return None
    if isinstance(blobs, dict):
        blobs[file_id] = loaded
    return loaded


def forget_blob(store: Any, file_id: uuid.UUID) -> None:
    book = getattr(store, "file_blobs", None)
    if isinstance(book, dict) and file_id in book:
        book.pop(file_id, None)


def snapshot_workspace(store: Any, run_id: uuid.UUID | None, tenant_id: object) -> int:
    """Copy workspace files that fit the cap onto the store."""
    if not isinstance(run_id, uuid.UUID) or not isinstance(tenant_id, uuid.UUID):
        return 0
    root = workspace_root(run_id)
    workspace = root / "workspace"
    if not workspace.is_dir():
        return 0
    book = _book(store, "workspace_files")
    existing = {
        str(row.get("path")): row
        for row in book.values()
        if isinstance(row, dict) and row.get("run_id") == run_id
    }
    changed = 0
    kept: dict[str, bytes] = {}
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.name.startswith("_"):
            continue
        rel = _relative(workspace, path)
        if rel is None:
            continue
        data = path.read_bytes()
        if not data or len(data) > _MAX_WORKSPACE_FILE:
            continue
        kept[rel] = data
    used = 0
    bounded: dict[str, bytes] = {}
    for rel, data in kept.items():
        if used + len(data) > _MAX_WORKSPACE:
            continue
        bounded[rel] = data
        used += len(data)
    kept = bounded
    for rel, data in kept.items():
        prior = existing.get(rel)
        prior_body = prior.get("body") if isinstance(prior, dict) else None
        if prior_body == data:
            continue
        row_id = prior.get("id") if isinstance(prior, dict) else new_id()
        if not isinstance(row_id, uuid.UUID):
            row_id = new_id()
        book[row_id] = {
            "id": row_id,
            "tenant_id": tenant_id,
            "run_id": run_id,
            "path": rel,
            "body": data,
            "size_bytes": len(data),
            "created_at": prior.get("created_at") if isinstance(prior, dict) else utcnow(),
            "updated_at": utcnow(),
        }
        changed += 1
    if changed:
        remember(
            store,
            tenant_id=tenant_id,
            actor_id="system",
            action="workspace.saved",
            target_type="run",
            target_id=run_id,
            detail={"files": changed, "bytes": sum(len(item) for item in kept.values())},
        )
    return changed


def restore_workspace(store: Any, arguments: dict[str, object]) -> int:
    """Write durable workspace bytes back, including an interrupted earlier run."""
    run_id = arguments.get("_run_id")
    tenant_id = arguments.get("_tenant_id")
    if not isinstance(run_id, uuid.UUID):
        return 0
    root = workspace_root(run_id)
    workspace = root / "workspace"
    wrote = _write_rows(workspace, _rows_for(store, run_id))
    if wrote or _has_files(workspace):
        return wrote
    prior = _prior_run(store, arguments.get("_conversation_id"), run_id)
    if prior is None or not isinstance(tenant_id, uuid.UUID):
        return 0
    copied = _copy_run(store, prior, run_id, tenant_id)
    wrote = _write_rows(workspace, _rows_for(store, run_id))
    if wrote:
        from ar_domain.jobs.progress import note_job  # noqa: PLC0415

        note_job(
            store,
            arguments,
            kind="workspace",
            tool_name="workspace.restore",
            label="Workspace",
            completed=wrote,
            total=wrote,
            status="completed",
            detail=f"Restored {wrote} files from the interrupted run.",
        )
    return wrote if wrote else copied


def materialise_file(store: Any, row: dict[str, object]) -> None:
    """Put a loaded blob back on the file cache."""
    file_id = row.get("id")
    if not isinstance(file_id, uuid.UUID):
        return
    files = getattr(store, "files", None)
    if isinstance(files, dict) and file_id not in files:
        files[file_id] = {
            "id": file_id,
            "tenant_id": row.get("tenant_id"),
            "owner_user_id": row.get("owner_user_id"),
            "conversation_id": row.get("conversation_id"),
            "run_id": row.get("run_id"),
            "kind": row.get("kind") or "upload",
            "name": row.get("name") or "file",
            "mime_type": row.get("mime_type") or "application/octet-stream",
            "size_bytes": row.get("size_bytes") or 0,
            "sha256": row.get("sha256"),
            "object_key": f"blob/{file_id}",
            "status": "ready",
            "scan_status": "skipped",
            "preview": {},
            "created_at": row.get("created_at") or utcnow(),
            "deleted_at": None,
        }
    body = _body(row)
    blobs = getattr(store, "blobs", None)
    if body is not None and isinstance(blobs, dict):
        blobs[file_id] = body


def _book(store: Any, name: str) -> dict[object, object]:
    current = getattr(store, name, None)
    if isinstance(current, dict):
        return current
    fresh: dict[object, object] = {}
    setattr(store, name, fresh)
    return fresh


def _row(store: Any, name: str, key: object) -> dict[str, object] | None:
    book = getattr(store, name, None)
    if not isinstance(book, dict):
        return None
    found = book.get(key)
    return found if isinstance(found, dict) else None


def _body(row: dict[str, object] | None) -> bytes | None:
    if row is None:
        return None
    body = row.get("body")
    if isinstance(body, (bytes, bytearray, memoryview)) and body:
        return bytes(body)
    return None


def _has_files(workspace: Path) -> bool:
    if not workspace.is_dir():
        return False
    return any(path.is_file() for path in workspace.rglob("*"))


def _relative(workspace: Path, path: Path) -> str | None:
    try:
        rel = path.relative_to(workspace).as_posix()
    except ValueError:
        return None
    if not rel or rel.startswith(".") or "/." in f"/{rel}" or ".." in rel.split("/"):
        return None
    if len(rel) > 240:
        return None
    return rel


def _rows_for(store: Any, run_id: uuid.UUID) -> list[dict[str, object]]:
    book = getattr(store, "workspace_files", None)
    if not isinstance(book, dict):
        return []
    return [
        row
        for row in book.values()
        if isinstance(row, dict) and row.get("run_id") == run_id and _body(row)
    ]


def _write_rows(workspace: Path, rows: list[dict[str, object]]) -> int:
    wrote = 0
    for row in rows:
        rel = str(row.get("path") or "")
        data = _body(row)
        if not rel or data is None or ".." in rel.split("/"):
            continue
        target = workspace / rel
        if target.is_file() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        wrote += 1
    return wrote


def _prior_run(store: Any, conversation_id: object, current: uuid.UUID) -> uuid.UUID | None:
    runs = getattr(store, "runs", None)
    if not isinstance(runs, dict) or not isinstance(conversation_id, uuid.UUID):
        return None
    found: list[dict[str, object]] = []
    for run in runs.values():
        if not isinstance(run, dict) or run.get("id") == current:
            continue
        if run.get("conversation_id") != conversation_id:
            continue
        run_id = run.get("id")
        if not isinstance(run_id, uuid.UUID) or not _rows_for(store, run_id):
            continue
        error = run.get("error")
        code = error.get("code") if isinstance(error, dict) else ""
        if str(run.get("status")) in {"failed", "cancelled"} or code == "interrupted":
            found.append(run)
    if not found:
        return None
    found.sort(key=lambda item: str(item.get("ended_at") or item.get("created_at") or ""))
    chosen = found[-1].get("id")
    return chosen if isinstance(chosen, uuid.UUID) else None


def _copy_run(store: Any, source: uuid.UUID, target: uuid.UUID, tenant_id: uuid.UUID) -> int:
    book = _book(store, "workspace_files")
    copied = 0
    for row in _rows_for(store, source):
        data = _body(row)
        rel = str(row.get("path") or "")
        if data is None or not rel:
            continue
        row_id = new_id()
        book[row_id] = {
            "id": row_id,
            "tenant_id": tenant_id,
            "run_id": target,
            "path": rel,
            "body": data,
            "size_bytes": len(data),
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        copied += 1
    return copied


def _load_blob(store: Any, file_id: uuid.UUID) -> bytes | None:
    rows = _sync_rows(store, "SELECT * FROM file_blobs WHERE id = :id", {"id": file_id})
    if not rows:
        return None
    row = rows[0]
    body = row.get("body")
    if not isinstance(body, (bytes, bytearray, memoryview)):
        return None
    data = bytes(body)
    row["body"] = data
    book = _book(store, "file_blobs")
    book[file_id] = row
    materialise_file(store, row)
    return data or None


def _sync_rows(store: Any, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
    engine = getattr(store, "durable_engine", None)
    sync = getattr(engine, "sync_engine", None)
    if sync is None:
        return []
    try:
        with sync.connect() as connection:
            result = connection.execute(text(sql), params)
            return [dict(row) for row in result.mappings()]
    except Exception:  # noqa: BLE001 — a cache miss stays a miss when Postgres is down
        return []


def clear_workspace_dir(run_id: uuid.UUID) -> None:
    """Remove a temp workspace. Tests use this to imitate a process restart."""
    root = workspace_root(run_id)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
