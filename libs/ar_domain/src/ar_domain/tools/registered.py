"""Run a registered script at a fixed entry point and record hashes.

The command comes from ``AR_REGISTERED_SCRIPT_ENTRY``. The model chooses the
script and the parameter object, not the command. The script runs through the
same computer path as ``general.code``. Numbers in the output are whatever the
script printed.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING

import orjson

from ar_common.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any


def dispatch_run_entry(store: Any, arguments: dict[str, object]) -> dict[str, object] | None:
    return run_entry(store, arguments)


def run_entry(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    script = _script_bytes(store, arguments)
    if isinstance(script, dict):
        return script
    params = arguments.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return _error("validation_failed", "params must be an object.")
    from ar_domain.tools.general import _limits, _prepare, _run_script  # noqa: PLC0415

    limits = _limits(store, arguments, "run_entry")
    root = _prepare(store, arguments)
    workspace = root / "workspace"
    (workspace / "model.py").write_bytes(script)
    params_bytes = orjson.dumps(params)
    (workspace / "params.json").write_bytes(params_bytes)
    entry = get_settings().registered_script_entry.split()
    extra = tuple(entry[2:]) if len(entry) > 2 else ()
    finished = _run_script(
        store,
        arguments,
        root,
        "model.py",
        command=["python3"],
        limits=limits,
        args=extra,
    )
    if isinstance(finished, dict):
        return finished
    outputs = _output_hashes(workspace)
    run_id = str(arguments.get("_run_id") or "")
    cited = {
        "run_id": run_id,
        "script_sha256": _sha(script),
        "params_sha256": _sha(params_bytes),
        "output_hashes": outputs,
    }
    text = finished.stdout.rstrip("\n")
    text = f"{text}\n{orjson.dumps(cited).decode()}" if text else orjson.dumps(cited).decode()
    return {
        "text": text,
        "structured": {
            "ok": finished.exit_code == 0,
            "exit_code": finished.exit_code,
            "stdout": finished.stdout,
            "stderr": finished.stderr,
            "command": entry,
            "run_id": run_id,
            "script_sha256": cited["script_sha256"],
            "params_sha256": cited["params_sha256"],
            "output_hashes": outputs,
        },
        "is_error": finished.exit_code != 0,
    }


def _output_hashes(workspace: Path) -> list[dict[str, object]]:
    skip = {"model.py", "params.json"}
    found: list[dict[str, object]] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.name in skip:
            continue
        if "inputs" in path.relative_to(workspace).parts:
            continue
        blob = path.read_bytes()
        found.append(
            {"name": str(path.relative_to(workspace)), "sha256": _sha(blob), "bytes": len(blob)}
        )
    return found


def _script_bytes(store: Any, arguments: dict[str, object]) -> bytes | dict[str, object]:
    file_id = arguments.get("fileId") or arguments.get("file_id")
    try:
        key = uuid.UUID(str(file_id))
    except TypeError, ValueError:
        return _error("validation_failed", "fileId is required.")
    blobs = getattr(store, "blobs", {})
    blob = blobs.get(key) if isinstance(blobs, dict) else None
    if isinstance(blob, bytes):
        return blob
    files = getattr(store, "files", {})
    row = files.get(key) if isinstance(files, dict) else None
    if isinstance(row, dict):
        data = row.get("data")
        if isinstance(data, bytes):
            return data
        from ar_common.errors import ArError  # noqa: PLC0415
        from ar_domain.files.objects import fetch_bytes  # noqa: PLC0415

        try:
            found = fetch_bytes(store, row)
        except ArError as exc:
            return _error("unavailable", str(exc))
        if isinstance(found, bytes):
            return found
    return _error("not_found", "The registered script was not found.")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {"code": code}, "is_error": True, "code": code}
