"""File bytes and workspace files outside the process temp directory.

A file's bytes live in the object store (``ar_domain.files.objects``); this module reads
them through the process cache and keeps workspace files that fit the cap on the store so
a flush can write them.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import text

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember

if TYPE_CHECKING:
    from typing import Any

_MAX_WORKSPACE_FILE = 2 * 1024 * 1024
_MAX_WORKSPACE = 8 * 1024 * 1024


def workspace_root(run_id: uuid.UUID) -> Path:
    """Host directory for one run. The same path ``general`` tools already use."""
    base = Path(os.environ.get("TMPDIR", tempfile.gettempdir()))
    return base / "ar-run-workspaces" / str(run_id)


def read_blob(store: Any, file_id: uuid.UUID) -> bytes | None:
    """A file's bytes: from the process cache, else the object store.

    Files a release before this one kept in ``file_blobs`` are moved to the object store
    when the tenant is hydrated (``durable.m35._legacy_rows``), so this reads only the
    cache and the store. The ``file_blobs`` fallback is a last resort for a row seen
    without its object.
    """
    from ar_domain.files.objects import fetch_bytes, keep_bytes  # noqa: PLC0415

    blobs = getattr(store, "blobs", None)
    if isinstance(blobs, dict):
        found = blobs.get(file_id)
        if isinstance(found, (bytes, bytearray, memoryview)):
            return bytes(found)
    row = _file_row(store, file_id)
    if row is None:
        return None
    if row.get("deleted_at") is not None or row.get("status") == "deleted":
        return None
    data = fetch_bytes(store, row)
    if data is not None:
        return data
    legacy = _load_blob(store, file_id)
    if legacy is None:
        return None
    keep_bytes(store, row, legacy)
    return legacy


def _file_row(store: Any, file_id: uuid.UUID) -> dict[str, object] | None:
    """The file's row from the store, else from the table."""
    row = _row(store, "files", file_id)
    if row is not None:
        return row
    rows = _sync_rows(store, "SELECT * FROM files WHERE id = :id", {"id": file_id})
    if not rows:
        return None
    loaded = rows[0]
    files = getattr(store, "files", None)
    if isinstance(files, dict):
        files[file_id] = loaded
    return loaded


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
    """Write the run's saved files back, starting from the conversation's last turn.

    A conversation has one working folder as far as the person can tell: what an earlier
    turn wrote is there in the next. Each run keeps its own copy, so the first tool call
    of a run copies the files of the latest earlier run in the conversation.
    """
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
    if wrote and _interrupted(store, prior):
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
    """The latest other run of the conversation that saved files."""
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
        if isinstance(run_id, uuid.UUID) and _rows_for(store, run_id):
            found.append(run)
    if not found:
        return None
    found.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("id"))))
    chosen = found[-1].get("id")
    return chosen if isinstance(chosen, uuid.UUID) else None


def _interrupted(store: Any, run_id: uuid.UUID) -> bool:
    run = store.runs.get(run_id)
    if not isinstance(run, dict):
        return False
    error = run.get("error")
    code = error.get("code") if isinstance(error, dict) else ""
    return str(run.get("status")) in {"failed", "cancelled"} or code == "interrupted"


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
    """Bytes a release before this one kept in Postgres (``file_blobs``)."""
    rows = _sync_rows(store, "SELECT body FROM file_blobs WHERE id = :id", {"id": file_id})
    if not rows:
        return None
    body = rows[0].get("body")
    if not isinstance(body, (bytes, bytearray, memoryview)):
        return None
    return bytes(body) or None


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
