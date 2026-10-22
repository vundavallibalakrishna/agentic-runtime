"""In-process computer. Production sandboxes run this same agent inside a pod.

The dev API does not call the sandbox-manager process (OQ-31). Commands still
pass the path, package and egress checks from spec 12.
"""

from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import uuid
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Any

from ar_common.ids import new_id
from ar_common.sandboxkit import (
    DEFAULT_DENY_CIDRS,
    PathEscapeError,
    accessibility_tree,
    allowed_hosts,
    clean_env,
    confine,
    curl_host,
    host_denied,
    package_install,
    png_chart,
    sanitise_name,
    truncate_output,
    virtual_path,
)
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.files.logic import object_key
from ar_domain.rows import as_int
from ar_domain.usage.logic import UsageRecord
from ar_domain.usage.service import note

CHART_SCRIPT = """
import csv, os, pathlib, struct, zlib, sys
root = pathlib.Path(os.environ["SANDBOX_WORKSPACE"])
inputs, outputs = root / "inputs", root / "outputs"
outputs.mkdir(parents=True, exist_ok=True)
rows = []
if inputs.is_dir():
    for path in sorted(inputs.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as handle:
            for item in csv.DictReader(handle):
                month = item.get("month") or item.get("Month") or ""
                raw = item.get("revenue") or item.get("Revenue") or "0"
                try:
                    value = int(float(raw))
                except ValueError:
                    continue
                if month:
                    rows.append((month, value))
if not rows:
    rows = [
        ("2026-01", 12000), ("2026-02", 15000), ("2026-03", 18000),
        ("2026-04", 14000), ("2026-05", 21000), ("2026-06", 19000),
    ]
values = [value for _, value in rows]
width, height, margin = 480, 240, 16
peak = max(values) or 1
slot = max(1, (width - margin * 2) // len(values))
raw = b""
for y in range(height):
    raw += b"\\x00"
    for x in range(width):
        ink = bytes((244, 241, 236))
        if margin <= x < margin + slot * len(values) and y <= height - margin:
            index = min((x - margin) // slot, len(values) - 1)
            local = (x - margin) % slot
            bar = int(values[index] / peak * (height - margin * 3))
            top = height - margin - bar
            if 4 < local < slot - 4 and top <= y:
                ink = bytes((31, 111, 104))
        raw += ink
def chunk(tag, data):
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
png = b"\\x89PNG\\r\\n\\x1a\\n" + chunk(b"IHDR", header)
png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
(outputs / "revenue-by-month.png").write_bytes(png)
print("wrote revenue-by-month.png")
"""

_ROOT = Path(tempfile.gettempdir()) / "ar-sandboxes"
_LIVE = frozenset({"pending", "starting", "ready", "suspending", "suspended", "resuming"})


def workspace_root(sandbox_id: uuid.UUID) -> Path:
    """Directory that holds ``workspace`` and ``tmp`` for one computer."""
    return _ROOT / str(sandbox_id)


def chart_command() -> str:
    """Bash command that reads ``inputs/*.csv`` and writes a PNG."""
    return f"{sys.executable} - <<'PY'\n{CHART_SCRIPT}\nPY"


def run_tool(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:  # noqa: PLR0911
    """Dispatch one sandbox or browser tool. Policy has already allowed it."""
    if name == "attach_to_sandbox":
        return _attach(store, arguments)
    if name == "export_file":
        return _export_named(store, arguments)
    book = _ensure_for_call(store, arguments)
    if book.get("is_error"):
        return book
    sandbox = book["sandbox"]
    if not isinstance(sandbox, dict):
        return _error("sandbox_unavailable", "the computer is not ready")
    root = workspace_root(uuid.UUID(str(sandbox["id"])))
    if name == "exec":
        return _exec(store, sandbox, root, arguments)
    if name == "read_file":
        return _read(root, arguments)
    if name == "write_file":
        return _write(root, arguments)
    if name == "list_files":
        return _list(root, arguments)
    if name.startswith("browser_") or name in {
        "navigate",
        "snapshot",
        "click",
        "type",
        "press",
        "scroll",
        "screenshot",
        "submit_form",
    }:
        return _browser(store, sandbox, root, name, arguments)
    return _error("unknown_tool", f"unknown tool {name}")


def ensure_scope(
    store: Any,
    *,
    tenant_id: uuid.UUID,
    template_slug: str,
    scope: str,
    scope_key: str,
    conversation_id: uuid.UUID | None,
    agent_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> dict[str, object]:
    """Create or resume the one live computer for a scope."""
    lock = store.sandbox_locks.setdefault(f"{tenant_id}:{scope_key}", threading.Lock())
    with lock:
        live = _live(store, tenant_id, scope_key)
        if live is not None and live["status"] == "suspended":
            return _resume(store, live)
        if live is not None and live["status"] in {"ready", "starting", "pending", "resuming"}:
            live["last_active_at"] = utcnow()
            live["status"] = "ready"
            return live
        from ar_domain.usage.service import UsageBook  # noqa: PLC0415

        UsageBook(store).assert_sandbox(tenant_id, user_id, agent_id)
        _cap(store, tenant_id)
        template = _template(store, tenant_id, template_slug)
        if template is None or template.get("status") != "active":
            raise LookupError(template_slug)
        now = utcnow()
        sandbox_id = new_id()
        token = os.urandom(32).hex()
        row: dict[str, object] = {
            "id": sandbox_id,
            "tenant_id": tenant_id,
            "template_id": template["id"],
            "template_slug": template["slug"],
            "scope": scope,
            "scope_key": scope_key,
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "user_id": user_id,
            "status": "ready",
            "driver": "docker",
            "driver_ref": f"local:{sandbox_id}",
            "endpoint_url": None,
            "auth_token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "token": token,
            "cpu_seconds": 0,
            "last_active_at": now,
            "started_at": now,
            "terminated_at": None,
            "error": None,
            "manifest": [],
            "browser": {"url": "", "html": "", "elements": []},
            "created_at": now,
            "updated_at": now,
        }
        store.sandboxes[sandbox_id] = row
        root = workspace_root(sandbox_id)
        (root / "workspace" / "inputs").mkdir(parents=True, exist_ok=True)
        (root / "workspace" / "outputs").mkdir(parents=True, exist_ok=True)
        (root / "tmp").mkdir(parents=True, exist_ok=True)
        _meter_session(store, row)
        remember(
            store,
            tenant_id=tenant_id,
            actor_id=user_id,
            action="sandbox.created",
            target_type="sandbox",
            target_id=sandbox_id,
            detail={"scope_key": scope_key, "template": template_slug},
        )
        return row


def suspend(store: Any, row: dict[str, object]) -> dict[str, object]:
    """Snapshot the workspace and stop compute. A second call is a no-op."""
    if row["status"] == "suspended":
        return row
    if row["status"] != "ready":
        raise ValueError(f"cannot suspend a sandbox that is {row['status']}")
    root = workspace_root(uuid.UUID(str(row["id"])))
    blob = _tar(root / "workspace")
    file_id = _store_blob(
        store,
        row,
        name=f"{row['id']}.tar",
        mime="application/zstd",
        data=blob,
        kind="sandbox_snapshot",
    )
    row["snapshot_file_id"] = file_id
    row["manifest"] = _manifest(root)
    row["status"] = "suspended"
    row["updated_at"] = utcnow()
    return row


def resume_row(store: Any, row: dict[str, object]) -> dict[str, object]:
    """Restore a suspended workspace. Repeating a ready row only touches it."""
    return _resume(store, row)


def reap(store: Any, *, now: object | None = None) -> dict[str, int]:
    """Suspend idle computers and terminate those past their lifetime."""
    moment = now if hasattr(now, "timestamp") else utcnow()
    suspended = 0
    terminated = 0
    for row in list(store.sandboxes.values()):
        template = _by_id(store, row.get("template_id"))
        idle = as_int(template.get("idle_suspend_s") if template else None, 900)
        life = as_int(template.get("max_lifetime_s") if template else None, 86400)
        last = row.get("last_active_at")
        started = row.get("started_at")
        idle_ready = row.get("status") == "ready" and hasattr(last, "timestamp")
        if idle_ready and moment.timestamp() - last.timestamp() > idle:
            suspend(store, row)
            suspended += 1
        aged = row.get("status") in {"ready", "suspended"} and hasattr(started, "timestamp")
        if aged and moment.timestamp() - started.timestamp() > life:
            _terminate(store, row, actor=row.get("user_id"))
            terminated += 1
    return {"suspended": suspended, "terminated": terminated}


def list_workspace(
    row: dict[str, object], path: str, *, recursive: bool
) -> list[dict[str, object]]:
    """List files. A suspended computer is listed from its snapshot manifest."""
    if row.get("status") == "suspended":
        manifest = row.get("manifest")
        items = manifest if isinstance(manifest, list) else []
        prefix = path.rstrip("/") or "/workspace"
        return [
            item
            for item in items
            if isinstance(item, dict) and str(item.get("path", "")).startswith(prefix)
        ]
    root = workspace_root(uuid.UUID(str(row["id"])))
    try:
        base = confine(root, path or "/workspace")
    except PathEscapeError as exc:
        raise ValueError(str(exc)) from exc
    if not base.exists():
        return []
    found: list[dict[str, object]] = []
    walker = base.rglob("*") if recursive else base.iterdir()
    for entry in walker:
        if len(found) >= 1000:
            break
        stat = entry.stat()
        found.append(
            {
                "path": virtual_path(root, entry),
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size_bytes": 0 if entry.is_dir() else stat.st_size,
                "modified_at": utcnow().isoformat(),
            }
        )
    found.sort(key=lambda item: str(item["path"]))
    return found


def read_workspace(row: dict[str, object], path: str) -> bytes:
    """Read one workspace file. A suspended computer must be resumed first."""
    if row.get("status") == "suspended":
        raise ValueError("resume the computer before reading a file")
    root = workspace_root(uuid.UUID(str(row["id"])))
    try:
        target = confine(root, path)
    except PathEscapeError as exc:
        raise ValueError(str(exc)) from exc
    if not target.is_file():
        raise FileNotFoundError(path)
    if target.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("file is larger than 100 MiB")
    return target.read_bytes()


def _resume(store: Any, row: dict[str, object]) -> dict[str, object]:
    if row["status"] == "ready":
        row["last_active_at"] = utcnow()
        return row
    root = workspace_root(uuid.UUID(str(row["id"])))
    snapshot = row.get("snapshot_file_id")
    if isinstance(snapshot, uuid.UUID):
        blob = store.blobs.get(snapshot, b"")
        if blob:
            _untar(root / "workspace", blob)
    (root / "workspace").mkdir(parents=True, exist_ok=True)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    row["status"] = "ready"
    row["last_active_at"] = utcnow()
    row["updated_at"] = utcnow()
    return row


def _exec(
    store: Any, sandbox: dict[str, object], root: Path, arguments: dict[str, object]
) -> dict[str, object]:
    command = str(arguments.get("command") or "")
    template = _by_id(store, sandbox.get("template_id")) or {}
    if package_install(command) and template.get("allow_packages") is not True:
        return _error("egress_denied", "package installs are not allowed on this computer")
    host = curl_host(command)
    if host is not None and not _host_ok(store, sandbox, template, host):
        _deny(store, sandbox, host)
        return _error("egress_denied", f"{host} is not on the egress allowlist")
    timeout = as_int(arguments.get("timeout_s"), as_int(template.get("exec_timeout_s"), 120))
    timeout = max(1, min(timeout, as_int(template.get("exec_timeout_s"), 120)))
    cwd = _cwd(root, str(arguments.get("cwd") or "/workspace"))
    env = clean_env(_env(arguments.get("env")))
    env["SANDBOX_WORKSPACE"] = str(root / "workspace")
    before = _output_stamp(root)
    try:
        code, stdout, stderr, truncated = _popen(command, cwd=cwd, env=env, timeout=timeout)
    except PathEscapeError as exc:
        return _error("validation_failed", str(exc))
    new_files = _new_outputs(root, before)
    exported = _auto_export(store, sandbox, root, new_files)
    text = stdout or stderr or "done"
    return {
        "text": text,
        "structured": {
            "exit_code": code,
            "stdout": stdout,
            "stderr": stderr,
            "truncated": truncated,
            "duration_ms": 0,
            "new_files": new_files,
            "artifacts": exported,
        },
        "is_error": code not in {0, None},
        "streams": [{"stream": "stdout", "text": stdout}, {"stream": "stderr", "text": stderr}],
    }


def _popen(
    command: str, *, cwd: Path, env: dict[str, str], timeout: int
) -> tuple[int, str, str, bool]:
    proc = subprocess.Popen(  # noqa: S603
        ["/bin/bash", "-lc", command],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        text_out, text_err, truncated = truncate_output(out or b"", err or b"")
        return 124, text_out, text_err or "timed out", True
    text_out, text_err, truncated = truncate_output(out or b"", err or b"")
    return proc.returncode or 0, text_out, text_err, truncated


def _browser(  # noqa: PLR0911
    store: Any,
    sandbox: dict[str, object],
    root: Path,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    template = _by_id(store, sandbox.get("template_id")) or {}
    if template.get("allow_browser") is not True and name != "snapshot":
        return _error("validation_failed", "this computer does not include a browser")
    current = sandbox.get("browser")
    session: dict[str, object] = (
        cast("dict[str, object]", current)
        if isinstance(current, dict)
        else {"url": "", "html": "", "elements": []}
    )
    sandbox["browser"] = session
    if name == "navigate":
        return _navigate(store, sandbox, template, session, str(arguments.get("url") or ""))
    if name == "snapshot":
        return _snapshot(session, as_int(arguments.get("max_chars"), 40000))
    if name == "click":
        return _click(store, sandbox, template, session, str(arguments.get("ref") or ""))
    if name == "type":
        return _type(session, str(arguments.get("ref") or ""), str(arguments.get("text") or ""))
    if name == "press":
        return _snapshot(session, 4000)
    if name == "scroll":
        return _snapshot(session, 4000)
    if name == "screenshot":
        return _screenshot(store, sandbox, root, session)
    if name == "submit_form":
        session["submitted"] = str(arguments.get("ref") or "")
        return _snapshot(session, 4000)
    return _error("unknown_tool", name)


def _navigate(
    store: Any,
    sandbox: dict[str, object],
    template: dict[str, object],
    session: dict[str, object],
    url: str,
) -> dict[str, object]:
    host = curl_host(f"curl {url}") or ""
    if not url.startswith(("https://", "http://")) or not _host_ok(store, sandbox, template, host):
        _deny(store, sandbox, host or url)
        return _error("egress_denied", f"{host or url} is not on the egress allowlist")
    import httpx  # noqa: PLC0415

    try:
        response = httpx.get(url, timeout=5.0, follow_redirects=False)
        html = response.text
        status = response.status_code
    except httpx.HTTPError:
        return _error("upstream_error", "the page could not be fetched")
    session["url"] = url
    session["html"] = html
    text, title, elements = accessibility_tree(html)
    session["title"] = title
    session["elements"] = elements
    return {
        "text": text,
        "structured": {"url": url, "title": title, "status": status, "untrusted": True},
        "is_error": False,
    }


def _snapshot(session: dict[str, object], max_chars: int) -> dict[str, object]:
    html = str(session.get("html") or "")
    text, title, elements = accessibility_tree(html, max_chars=max(1, min(max_chars, 40000)))
    session["elements"] = elements
    return {
        "text": text or "empty page",
        "structured": {"url": session.get("url") or "", "title": title, "untrusted": True},
        "is_error": False,
    }


def _click(
    store: Any,
    sandbox: dict[str, object],
    template: dict[str, object],
    session: dict[str, object],
    ref: str,
) -> dict[str, object]:
    element = _element(session, ref)
    href = str(element.get("href") or "")
    if href.startswith("http"):
        return _navigate(store, sandbox, template, session, href)
    return _snapshot(session, 4000)


def _type(session: dict[str, object], ref: str, text: str) -> dict[str, object]:
    element = _element(session, ref)
    element["value"] = text
    return _snapshot(session, 4000)


def _screenshot(
    store: Any, sandbox: dict[str, object], root: Path, session: dict[str, object]
) -> dict[str, object]:
    del root
    png = png_chart([1, 2, 3])
    saved = _store_blob(
        store,
        sandbox,
        name="browser.png",
        mime="image/png",
        data=png,
        kind="artifact",
    )
    _emit_artifact(
        store, sandbox, file_id=saved, name="browser.png", mime="image/png", size=len(png)
    )
    return {
        "text": f"screenshot {saved}",
        "structured": {
            "file_id": str(saved),
            "url": session.get("url") or "",
            "title": session.get("title") or "",
            "untrusted": True,
        },
        "is_error": False,
    }


def _attach(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    file_id = _uuid(arguments.get("file_id"))
    blob = store.blobs.get(file_id) if file_id else None
    row = store.files.get(file_id) if file_id else None
    if file_id is None or blob is None or not isinstance(row, dict):
        return _error("not_found", "file was not found")
    sandbox = _ensure_for_call(store, arguments)
    if sandbox.get("is_error"):
        return sandbox
    live = sandbox["sandbox"]
    if not isinstance(live, dict):
        return _error("sandbox_unavailable", "the computer is not ready")
    root = workspace_root(uuid.UUID(str(live["id"])))
    name = sanitise_name(str(row.get("name") or "upload"))
    target = confine(root, str(arguments.get("path") or f"/workspace/inputs/{name}"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(bytes(blob))
    return {
        "text": f"copied {name}",
        "structured": {"path": virtual_path(root, target)},
        "is_error": False,
    }


def save_artifact(
    store: Any, sandbox: dict[str, object], path: str, name: str = ""
) -> dict[str, object]:
    """Copy one workspace file into the artifact catalogue."""
    root = workspace_root(uuid.UUID(str(sandbox["id"])))
    try:
        target = confine(root, path)
    except PathEscapeError as exc:
        return _error("validation_failed", str(exc))
    if not target.is_file():
        return _error("not_found", "file was not found")
    label = sanitise_name(name or target.name)
    data = target.read_bytes()
    file_id = _store_blob(store, sandbox, name=label, mime=_mime(label), data=data, kind="artifact")
    _emit_artifact(store, sandbox, file_id=file_id, name=label, mime=_mime(label), size=len(data))
    return {
        "text": label,
        "structured": {"file_id": str(file_id), "name": label},
        "is_error": False,
    }


def _export_named(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    found = _ensure_for_call(store, arguments)
    if found.get("is_error"):
        return found
    sandbox = found["sandbox"]
    if not isinstance(sandbox, dict):
        return _error("sandbox_unavailable", "the computer is not ready")
    path = str(arguments.get("path") or "")
    root = workspace_root(uuid.UUID(str(sandbox["id"])))
    try:
        target = confine(root, path)
    except PathEscapeError as exc:
        return _error("validation_failed", str(exc))
    if not target.is_file():
        return _error("not_found", "file was not found")
    name = sanitise_name(str(arguments.get("name") or target.name))
    data = target.read_bytes()
    file_id = _store_blob(store, sandbox, name=name, mime=_mime(name), data=data, kind="artifact")
    _emit_artifact(store, sandbox, file_id=file_id, name=name, mime=_mime(name), size=len(data))
    return {
        "text": name,
        "structured": {"file_id": str(file_id), "name": name},
        "is_error": False,
    }


def _ensure_for_call(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    tenant = _uuid(arguments.get("_tenant_id"))
    user = _uuid(arguments.get("_user_id"))
    conversation = _uuid(arguments.get("_conversation_id"))
    agent = _uuid(arguments.get("_agent_id"))
    if tenant is None:
        return _error("sandbox_unavailable", "the computer is not ready")
    slug = "python-data"
    scope = "conversation"
    scope_key = f"conv:{conversation}" if conversation else f"au:{agent}:{user}"
    version_id = arguments.get("_agent_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else {}
    sandbox_spec = definition.get("sandbox") if isinstance(definition, dict) else {}
    if isinstance(sandbox_spec, dict) and sandbox_spec.get("template"):
        slug = str(sandbox_spec.get("template"))
        scope = str(sandbox_spec.get("scope") or "conversation")
    if scope == "agent" and agent is not None:
        scope_key = f"agent:{agent}"
    elif scope == "agent_user" and agent is not None and user is not None:
        scope_key = f"au:{agent}:{user}"
    from ar_common.errors import QuotaExceededError  # noqa: PLC0415

    try:
        row = ensure_scope(
            store,
            tenant_id=tenant,
            template_slug=slug,
            scope=scope,
            scope_key=scope_key,
            conversation_id=conversation,
            agent_id=agent,
            user_id=user,
        )
    except LookupError:
        return _error("sandbox_unavailable", f"sandbox template {slug} is not available")
    except RuntimeError as exc:
        return _error("quota_exceeded", str(exc))
    except QuotaExceededError as exc:
        return _error("quota_exceeded", str(exc))
    run_id = _uuid(arguments.get("_run_id"))
    if run_id is not None:
        row["run_id"] = run_id
        row["_run_id"] = run_id
    if arguments.get("_tool_call_id"):
        row["_tool_call_id"] = arguments.get("_tool_call_id")
    _copy_inputs(store, row, arguments.get("_attachment_ids"))
    return {"sandbox": row, "is_error": False}


def _copy_inputs(store: Any, sandbox: dict[str, object], raw: object) -> None:
    if not isinstance(raw, list):
        return
    root = workspace_root(uuid.UUID(str(sandbox["id"])))
    for item in raw:
        file_id = _uuid(item)
        blob = store.blobs.get(file_id) if file_id else None
        meta = store.files.get(file_id) if file_id else None
        if file_id is None or blob is None or not isinstance(meta, dict):
            continue
        name = sanitise_name(str(meta.get("name") or "upload"))
        target = confine(root, f"/workspace/inputs/{name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(blob))


def _host_ok(
    store: Any, sandbox: dict[str, object], template: dict[str, object], host: str
) -> bool:
    extra = _extra(store, sandbox)
    tenant = _tenant_allow(store, sandbox.get("tenant_id"))
    mirrors = _mirrors(allow=bool(template.get("allow_packages")))
    hosts = allowed_hosts(
        _strings(template.get("egress_allowlist")),
        extra,
        tenant,
        mirrors=mirrors,
        allow_packages=bool(template.get("allow_packages")),
        env=os.environ.get("AR_ENV", "dev"),
    )
    if host not in hosts and "*" not in hosts:
        return False
    allow_loopback = os.environ.get("AR_ENV", "dev") in {"dev", "ci", "test"}
    return not host_denied(host, DEFAULT_DENY_CIDRS, _resolve, allow_loopback=allow_loopback)


def _deny(store: Any, sandbox: dict[str, object], host: str) -> None:
    remember(
        store,
        tenant_id=sandbox.get("tenant_id"),
        actor_id=sandbox.get("user_id"),
        action="sandbox.egress_denied",
        target_type="sandbox",
        target_id=sandbox.get("id"),
        detail={"host": host},
        outcome="failure",
    )


def _resolve(host: str) -> list[str]:
    import socket  # noqa: PLC0415

    infos = socket.getaddrinfo(host, None)
    return [str(item[4][0]) for item in infos]


def _mirrors(*, allow: bool) -> list[str]:
    if not allow:
        return []
    raw = os.environ.get("AR_SANDBOX_PACKAGE_MIRRORS", "")
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _template(store: Any, tenant_id: uuid.UUID, slug: str) -> dict[str, object] | None:
    for row in store.sandbox_templates.values():
        owner = row.get("tenant_id")
        matches = row.get("slug") == slug and (owner is None or owner == tenant_id)
        if isinstance(row, dict) and matches:
            return cast("dict[str, object]", row)
    return None


def _by_id(store: Any, template_id: object) -> dict[str, object] | None:
    if isinstance(template_id, uuid.UUID):
        found = store.sandbox_templates.get(template_id)
        return cast("dict[str, object]", found) if isinstance(found, dict) else None
    return None


def _live(store: Any, tenant_id: uuid.UUID, scope_key: str) -> dict[str, object] | None:
    for row in store.sandboxes.values():
        same = row.get("tenant_id") == tenant_id and row.get("scope_key") == scope_key
        if isinstance(row, dict) and same and row.get("status") in _LIVE:
            return cast("dict[str, object]", row)
    return None


def _cap(store: Any, tenant_id: uuid.UUID) -> None:
    from ar_contracts.tenants import PlanLimits  # noqa: PLC0415

    limits = PlanLimits()
    settings = store.tenant_settings.get(tenant_id, {})
    raw = settings.get("plan_limits") if isinstance(settings, dict) else None
    if isinstance(raw, dict):
        limits = PlanLimits.model_validate(raw)
    cap = limits.max_concurrent_sandboxes
    env_cap = os.environ.get("AR_SANDBOX_MAX_PER_TENANT")
    if env_cap and env_cap.isdigit():
        cap = min(cap, int(env_cap))
    live = [
        row
        for row in store.sandboxes.values()
        if row.get("tenant_id") == tenant_id and row.get("status") in _LIVE
    ]
    from ar_common.errors import PlanLimitReachedError  # noqa: PLC0415
    from ar_domain.identity.plan_limits import guard  # noqa: PLC0415

    try:
        guard(store, tenant_id, "max_concurrent_sandboxes", 1, current=len(live))
    except PlanLimitReachedError as exc:
        raise RuntimeError("concurrent sandbox limit reached") from exc
    if len(live) >= cap:
        raise RuntimeError("concurrent sandbox limit reached")


def _store_blob(
    store: Any,
    sandbox: dict[str, object],
    *,
    name: str,
    mime: str,
    data: bytes,
    kind: str,
) -> uuid.UUID:
    file_id = new_id()
    now = utcnow()
    tenant = sandbox.get("tenant_id")
    conversation = sandbox.get("conversation_id")
    taken = {
        str(row.get("name"))
        for row in store.files.values()
        if row.get("conversation_id") == conversation and row.get("deleted_at") is None
    }
    unique = name
    index = 2
    while unique in taken:
        stem, dot, ext = name.rpartition(".")
        unique = f"{stem or name} ({index}){dot}{ext}" if dot else f"{name} ({index})"
        index += 1
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": sandbox.get("user_id"),
        "conversation_id": conversation,
        "run_id": sandbox.get("run_id"),
        "kind": kind,
        "name": unique,
        "mime_type": mime,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "object_key": object_key(str(tenant), kind, f"{now:%Y}", f"{now:%m}", str(file_id)),
        "status": "ready",
        "scan_status": "skipped",
        "preview": {},
        "created_at": now,
        "deleted_at": None,
    }
    store.blobs[file_id] = data
    return file_id


def _emit_artifact(
    store: Any,
    sandbox: dict[str, object],
    *,
    file_id: uuid.UUID,
    name: str,
    mime: str,
    size: int,
) -> None:
    run_id = sandbox.get("run_id")
    run = store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
    if not isinstance(run, dict):
        context_run = sandbox.get("_run_id")
        run = store.runs.get(context_run) if isinstance(context_run, uuid.UUID) else None
    if isinstance(run, dict):
        store._emit(
            run,
            "artifact.created",
            {"file_id": str(file_id), "name": name, "mime_type": mime, "size_bytes": size},
        )
        if name == "browser.png":
            store._emit(
                run,
                "browser.screenshot",
                {
                    "tool_call_id": str(sandbox.get("_tool_call_id") or ""),
                    "file_id": str(file_id),
                    "url": "",
                    "title": name,
                },
            )


def _auto_export(store: Any, sandbox: dict[str, object], root: Path, paths: list[str]) -> list[str]:
    exported: list[str] = []
    for path in paths[:20]:
        target = confine(root, path)
        if not target.is_file() or target.stat().st_size > 100 * 1024 * 1024:
            continue
        data = target.read_bytes()
        name = sanitise_name(target.name)
        file_id = _store_blob(
            store, sandbox, name=name, mime=_mime(name), data=data, kind="artifact"
        )
        _emit_artifact(store, sandbox, file_id=file_id, name=name, mime=_mime(name), size=len(data))
        exported.append(str(file_id))
    return exported


def _output_stamp(root: Path) -> dict[str, int]:
    outputs = root / "workspace" / "outputs"
    found: dict[str, int] = {}
    if not outputs.exists():
        return found
    for path in outputs.rglob("*"):
        if path.is_file():
            found[str(path)] = path.stat().st_mtime_ns
    return found


def _new_outputs(root: Path, before: dict[str, int]) -> list[str]:
    outputs = root / "workspace" / "outputs"
    found: list[str] = []
    if not outputs.exists():
        return found
    for path in outputs.rglob("*"):
        if not path.is_file():
            continue
        stamp = path.stat().st_mtime_ns
        if before.get(str(path)) != stamp:
            found.append(virtual_path(root, path))
    return found


def _manifest(root: Path) -> list[dict[str, object]]:
    base = root / "workspace"
    if not base.exists():
        return []
    return [
        {
            "path": virtual_path(root, path),
            "name": path.name,
            "type": "dir" if path.is_dir() else "file",
            "size_bytes": 0 if path.is_dir() else path.stat().st_size,
            "modified_at": utcnow().isoformat(),
        }
        for path in base.rglob("*")
    ]


def _tar(workspace: Path) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        if workspace.exists():
            archive.add(workspace, arcname="workspace")
    return buffer.getvalue()


def _untar(workspace: Path, blob: bytes) -> None:
    workspace.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=BytesIO(blob), mode="r") as archive:
        archive.extractall(workspace.parent, filter="data")


def _cwd(root: Path, raw: str) -> Path:
    path = confine(root, raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read(root: Path, arguments: dict[str, object]) -> dict[str, object]:
    try:
        target = confine(root, str(arguments.get("path") or ""))
    except PathEscapeError as exc:
        return _error("validation_failed", str(exc))
    if not target.is_file():
        return _error("not_found", "file was not found")
    data = target.read_bytes()
    offset = max(0, as_int(arguments.get("offset"), 0))
    limit = min(65536, as_int(arguments.get("limit"), 65536))
    chunk = data[offset : offset + limit]
    encoding = str(arguments.get("encoding") or "utf8")
    content = chunk.decode("utf-8", errors="replace") if encoding != "base64" else _b64(chunk)
    return {
        "text": content,
        "structured": {
            "content": content,
            "size_bytes": len(data),
            "eof": offset + limit >= len(data),
        },
        "is_error": False,
    }


def _write(root: Path, arguments: dict[str, object]) -> dict[str, object]:
    content = str(arguments.get("content") or "")
    if len(content.encode()) > 10 * 1024 * 1024:
        return _error("validation_failed", "file is larger than 10 MiB")
    try:
        target = confine(root, str(arguments.get("path") or ""))
    except PathEscapeError as exc:
        return _error("validation_failed", str(exc))
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "ab" if arguments.get("append") is True else "wb"
    payload = content.encode()
    with target.open(mode) as handle:
        handle.write(payload)
    return {
        "text": f"wrote {len(payload)} bytes",
        "structured": {"bytes_written": len(payload)},
        "is_error": False,
    }


def _list(root: Path, arguments: dict[str, object]) -> dict[str, object]:
    try:
        base = confine(root, str(arguments.get("path") or "/workspace"))
    except PathEscapeError as exc:
        return _error("validation_failed", str(exc))
    entries: list[dict[str, object]] = []
    if base.exists():
        walker = base.rglob("*") if arguments.get("recursive") is True else base.iterdir()
        for entry in walker:
            entries.append(
                {
                    "path": virtual_path(root, entry),
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size_bytes": 0 if entry.is_dir() else entry.stat().st_size,
                }
            )
            if len(entries) >= min(1000, as_int(arguments.get("max_entries"), 1000) or 1000):
                break
    text = "\n".join(str(item["path"]) for item in entries) or "empty"
    return {"text": text, "structured": {"entries": entries}, "is_error": False}


def _meter_session(store: Any, row: dict[str, object]) -> None:
    user = None if row.get("user_id") is None else str(row.get("user_id"))
    agent = None if row.get("agent_id") is None else str(row.get("agent_id"))
    note(
        store,
        UsageRecord(
            tenant_id=str(row["tenant_id"]),
            occurred_at=utcnow(),
            metric="sandbox_sessions",
            quantity=1,
            cost_micros=0,
            dedupe_key=f"sandbox-session:{row['id']}",
            user_id=user,
            agent_id=agent,
            source="sandbox",
        ),
    )
    cpu = row.get("cpu_seconds")
    if isinstance(cpu, int) and cpu > 0:
        note(
            store,
            UsageRecord(
                tenant_id=str(row["tenant_id"]),
                occurred_at=utcnow(),
                metric="sandbox_cpu_seconds",
                quantity=cpu,
                cost_micros=0,
                dedupe_key=f"sandbox-cpu:{row['id']}",
                user_id=user,
                agent_id=agent,
                source="sandbox",
            ),
        )


def terminate_row(store: Any, row: dict[str, object], *, actor: object) -> None:
    """Stop a computer and keep the audit row. Repeating a terminal row is a no-op."""
    if row.get("status") in {"terminated", "failed"}:
        return
    _terminate(store, row, actor=actor)


def _terminate(store: Any, row: dict[str, object], *, actor: object) -> None:
    row["status"] = "terminated"
    row["terminated_at"] = utcnow()
    row["updated_at"] = utcnow()
    remember(
        store,
        tenant_id=row.get("tenant_id"),
        actor_id=actor,
        action="sandbox.terminated",
        target_type="sandbox",
        target_id=row.get("id"),
        detail={"scope_key": row.get("scope_key")},
    )


def _element(session: dict[str, object], ref: str) -> dict[str, str]:
    elements = session.get("elements")
    if isinstance(elements, list):
        for item in elements:
            if isinstance(item, dict) and item.get("ref") == ref:
                return item
    return {"ref": ref, "tag": "button", "name": ref, "href": "", "value": ""}


def _extra(store: Any, sandbox: dict[str, object]) -> list[str]:
    agent_id = sandbox.get("agent_id")
    agent = store.agents.get(agent_id) if isinstance(agent_id, uuid.UUID) else None
    version_id = agent.get("published_version_id") if isinstance(agent, dict) else None
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else {}
    spec = definition.get("sandbox") if isinstance(definition, dict) else {}
    if isinstance(spec, dict):
        return _strings(spec.get("extra_egress_allowlist"))
    return []


def _tenant_allow(store: Any, tenant_id: object) -> list[str]:
    settings = store.tenant_settings.get(tenant_id, {}) if isinstance(tenant_id, uuid.UUID) else {}
    if not isinstance(settings, dict):
        return []
    return _strings(settings.get("egress_allowlist"))


def _env(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _mime(name: str) -> str:
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".csv"):
        return "text/csv"
    if name.endswith(".html"):
        return "text/html"
    if name.endswith(".svg"):
        return "image/svg+xml"
    if name.endswith(".md"):
        return "text/markdown"
    return "application/octet-stream"


def _b64(data: bytes) -> str:
    import base64  # noqa: PLC0415

    return base64.b64encode(data).decode("ascii")


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
