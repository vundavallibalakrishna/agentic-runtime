#!/usr/bin/env python
"""Fail if a fake or stub model is wired into the install or product code.

The recorded model server lives under services/fake_llm and is imported by
tests. It must not appear in compose.yaml, image definitions, or any other
non-test source.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = (
    ROOT / "compose.yaml",
    ROOT / "compose.airgap.yaml",
    ROOT / "images",
    ROOT / "services",
    ROOT / "libs",
    ROOT / "apps",
    ROOT / "scripts",
    ROOT / "packs",
    ROOT / "deploy",
    ROOT / "Procfile.dev",
    ROOT / "Procfile.dev-min",
)
SKIP_PARTS = {
    "tests",
    "__pycache__",
    ".venv",
    "node_modules",
    "fake_llm",
    "e2e",
    "ar_testing",
}
SKIP_NAMES = {"check_no_fake_models.py", "pyproject.toml"}
PATTERN = re.compile(
    r"fake-llm|fake_llm|fake-chat|ar_fake_llm|AR_FAKE_LLM|fixture provider|"
    r"stub model|stub_reply|OpenAI-compatible stub|\bfaker\b",
    re.IGNORECASE,
)


def _skip(path: Path) -> bool:
    return bool(SKIP_PARTS.intersection(path.parts))


def main() -> int:
    hits: list[str] = []
    for start in SCAN:
        if not start.exists():
            continue
        files = [start] if start.is_file() else sorted(start.rglob("*"))
        for path in files:
            if not path.is_file() or _skip(path) or path.name in SKIP_NAMES:
                continue
            allowed = {".py", ".ts", ".tsx", ".yml", ".yaml", ".sh", ".md", ".toml"}
            named = path.name in {"Dockerfile", "Procfile.dev", "Procfile.dev-min"}
            docker = "Dockerfile" in path.name
            if path.suffix not in allowed and not named and not docker:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if PATTERN.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{number}:{line.strip()[:160]}")
    if hits:
        print("fake or stub model references outside test code:", file=sys.stderr)
        for hit in hits:
            print(hit, file=sys.stderr)
        return 1
    print("no fake or stub model in compose, images, or non-test source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
