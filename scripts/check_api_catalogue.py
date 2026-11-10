#!/usr/bin/env python
"""Fail when the API catalogue and openapi.json disagree on method and path.

Parameter names are compared as ``{}`` so ``{agentId}`` and ``{agent_id}`` are
the same route. CI runs this from the docs job (OQ-120).

Proof label: unit
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import orjson

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "docs/05-contracts/api-catalogue.md"
OPENAPI = ROOT / "openapi.json"
_METHOD = re.compile(
    r"^\|\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s*\|\s*(.+?)\s*\|",
    re.MULTILINE,
)
_PATH = re.compile(r"(/[^`\s)]+)")
_PARAM = re.compile(r"\{[^}]+\}")


def normalise(path: str) -> str:
    return _PARAM.sub("{}", path)


def catalogue_ops(text: str) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for method, cell in _METHOD.findall(text):
        paths = _PATH.findall(cell)
        if paths:
            found.add((method, normalise(paths[0])))
    return found


def openapi_ops(document: dict[str, object]) -> set[tuple[str, str]]:
    paths = document.get("paths")
    found: set[tuple[str, str]] = set()
    if not isinstance(paths, dict):
        return found
    verbs = {"get", "post", "put", "patch", "delete", "head", "options"}
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method in item:
            if method.lower() in verbs:
                found.add((method.upper(), normalise(str(path))))
    return found


def main() -> int:
    catalogue = CATALOGUE.read_text(encoding="utf-8")
    document = orjson.loads(OPENAPI.read_bytes())
    left = catalogue_ops(catalogue)
    right = openapi_ops(document)
    missing = sorted(right - left)
    extra = sorted(left - right)
    if not missing and not extra:
        return 0
    sys.stderr.write("api catalogue drifted from openapi.json\n")
    for method, path in missing:
        sys.stderr.write(f"  missing from catalogue: {method} {path}\n")
    for method, path in extra:
        sys.stderr.write(f"  not in openapi.json: {method} {path}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
