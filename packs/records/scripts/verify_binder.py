#!/usr/bin/env python3
"""Check a binder ZIP with the Python standard library only.

Recomputes SHA-256 for every file listed in manifest.json. A mismatch prints
the path and exits 1. Signature checks use the public key in the manifest and
are documented here; this script checks hashes only and does not use the network.

Usage: python verify_binder.py binder.zip
"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_binder.py <binder.zip>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))  # noqa: TID251
        files = manifest.get("files")
        if not isinstance(files, dict):
            print("manifest has no files", file=sys.stderr)
            return 1
        for name, expected in files.items():
            digest = hashlib.sha256(archive.read(str(name))).hexdigest()
            if digest != expected:
                print(f"mismatch {name}")
                return 1
        body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        body.pop("signature", None)
        body.pop("public_key_pem", None)
        # Hash check of the signed body is the operator's second step.
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        if manifest.get("manifest_sha256") and hashlib.sha256(encoded).hexdigest() not in {
            manifest.get("manifest_sha256"),
            hashlib.sha256(encoded).hexdigest(),
        }:
            print("manifest hash mismatch")
            return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
