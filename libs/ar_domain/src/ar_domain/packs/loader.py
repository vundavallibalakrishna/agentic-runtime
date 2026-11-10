"""Load signed pack manifests from a directory. Core does not name a pack."""

from __future__ import annotations

import importlib
import os
import sys
from typing import TYPE_CHECKING

import orjson

from ar_domain.agents.packs import verify_signature

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any


def load_pack_tree(app: Any, root: Path, *, require_signature: bool) -> None:
    """Mount every pack under ``root`` whose manifest verifies."""
    if not root.is_dir():
        return
    for manifest_path in sorted(root.glob("*/manifest.json")):
        load_manifest(app, manifest_path, require_signature=require_signature)


def load_manifest(app: Any, manifest_path: Path, *, require_signature: bool) -> None:
    pack_dir = manifest_path.parent
    manifest = orjson.loads(manifest_path.read_bytes())
    if not isinstance(manifest, dict):
        raise TypeError(f"{manifest_path} is not an object")
    _verify(pack_dir, manifest, require_signature=require_signature)
    extension = _extension(manifest)
    module_name = str(extension.get("entry") or "")
    if not module_name:
        return
    src = pack_dir / "src"
    inserted = False
    src_text = str(src)
    if src.is_dir() and src_text not in sys.path:
        sys.path.insert(0, src_text)
        inserted = True
    try:
        module = importlib.import_module(module_name)
    finally:
        if inserted:
            sys.path.remove(src_text)
    mount = getattr(module, "mount", None)
    if mount is not None:
        mount(app)


def _verify(pack_dir: Path, manifest: dict[str, object], *, require_signature: bool) -> None:
    signature_path = pack_dir / "signature.b64"
    key_path = pack_dir / "key.pub"
    signature = ""
    if signature_path.is_file():
        signature = signature_path.read_text(encoding="utf-8").strip()
    if not signature:
        if require_signature or os.environ.get("AR_PACK_SIGNATURE_REQUIRED") == "1":
            raise ValueError(f"{pack_dir.name} is unsigned")
        return
    if not key_path.is_file():
        raise ValueError(f"{pack_dir.name} has a signature and no public key")
    from ar_domain.agents.packs import manifest_digest  # noqa: PLC0415

    _hex, digest = manifest_digest(manifest)
    public = key_path.read_text(encoding="utf-8")
    if not verify_signature(public, signature, digest):
        raise ValueError(f"{pack_dir.name} signature is invalid")
    trusted = os.environ.get("AR_PACK_TRUSTED_KEYS", "")
    key_file = pack_dir / "key.id"
    key_id = key_file.read_text(encoding="utf-8").strip() if key_file.is_file() else ""
    if require_signature and key_id and key_id not in trusted.split(","):
        raise ValueError(f"{pack_dir.name} key is not trusted")


def _extension(manifest: dict[str, object]) -> dict[str, object]:
    spec = manifest.get("spec")
    if not isinstance(spec, dict):
        return {}
    extension = spec.get("extension")
    return extension if isinstance(extension, dict) else {}
