"""Run a registered script at a fixed entry point and record hashes.

The command comes from ``AR_REGISTERED_SCRIPT_ENTRY``. The model chooses the
script and the parameter object, not the command. Numbers in the output are
whatever the script printed.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

from ar_common.offload import blocking

if TYPE_CHECKING:
    from typing import Any


def dispatch_run_entry(store: Any, arguments: dict[str, object]) -> dict[str, object] | None:
    return run_entry(store, arguments)


def run_registered(
    script: bytes, params: dict[str, object], inputs: list[tuple[str, bytes]]
) -> dict[str, object]:
    """Run the configured entry point. The same bytes produce the same hashes."""
    entry = os.environ.get("AR_REGISTERED_SCRIPT_ENTRY", "python model.py --params params.json")
    parts = entry.split()
    if not parts:
        return {"ok": False, "error": "AR_REGISTERED_SCRIPT_ENTRY is empty"}
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / "model.py").write_bytes(script)
        (root / "params.json").write_bytes(orjson.dumps(params))
        input_hashes = []
        for name, data in inputs:
            safe = Path(name).name
            (root / safe).write_bytes(data)
            input_hashes.append({"name": safe, "sha256": _sha(data)})
        try:
            completed = blocking(
                lambda: subprocess.run(  # noqa: S603 — the entry point is an install setting
                    parts,
                    cwd=root,
                    check=False,
                    capture_output=True,
                    timeout=60,
                )
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "the script timed out"}
        outputs = []
        for path in sorted(root.iterdir()):
            if path.name in {"model.py", "params.json"} or not path.is_file():
                continue
            if any(path.name == item["name"] for item in input_hashes):
                continue
            blob = path.read_bytes()
            outputs.append({"name": path.name, "sha256": _sha(blob), "bytes": len(blob)})
        return {
            "ok": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout": completed.stdout.decode("utf-8", "replace"),
            "stderr": completed.stderr.decode("utf-8", "replace"),
            "command": parts,
            "script_sha256": _sha(script),
            "params_sha256": _sha(orjson.dumps(params)),
            "input_hashes": input_hashes,
            "output_hashes": outputs,
        }


def run_entry(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    script = _script_bytes(store, arguments)
    if isinstance(script, dict):
        return script
    params = arguments.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return _error("validation_failed", "params must be an object.")
    result = run_registered(script, params, [])
    if not result.get("ok") and result.get("error"):
        return _error("validation_failed", str(result["error"]))
    return {
        "text": str(result.get("stdout") or ""),
        "structured": result,
        "is_error": not result.get("ok"),
    }


def _script_bytes(store: Any, arguments: dict[str, object]) -> bytes | dict[str, object]:
    file_id = arguments.get("fileId") or arguments.get("file_id")
    try:
        key = uuid.UUID(str(file_id))
    except TypeError, ValueError:
        return _error("validation_failed", "fileId is required.")
    blobs = getattr(store, "blobs", {})
    if isinstance(blobs, dict) and isinstance(blobs.get(key), bytes):
        return blobs[key]
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
