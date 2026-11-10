"""Fail if core names an industry or the records product.

Allowlisted trees: ``packs/``, ``docs/``, and this script. Applied migrations and the
schema modules that mirror them may keep historical identifiers until a later revision
drops those tables. The stage 0 doc test quotes the principle on purpose.

Label: unit
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Framework and product terms. Case-insensitive.
FRAMEWORK = (
    r"soc\s*2",
    r"\bsoc2\b",
    r"\bnist\b",
    r"iso\s*27001",
    r"\bhipaa\b",
    r"\bgdpr\b",
    r"\bgxp\b",
    r"21\s*cfr",
    r"\bpharma\b",
    r"\bclinical\b",
    r"\bpatient\b",
    r"/admin/assurance",
)
PRODUCT = (
    r"\bbinders?\b",
    r"legal[\s-]+holds?",
    r"ai[\s-]+register",
    r"\bquestionnaire\b",
)
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".next",
    "dist",
    "build",
}
ALLOW_PREFIXES = ("packs/", "docs/")
ALLOW_FILES = {"AGENTS.md", "CLAUDE.md"}
# Historical schema identifiers stay until the drop revision.
SCHEMA_PREFIXES = (
    "libs/ar_domain/src/ar_domain/migrations/",
    "libs/ar_domain/src/ar_domain/records/tables.py",
    "libs/ar_domain/src/ar_domain/approvals/models.py",
)
STAGE0_TEST = "tests/unit/test_stage0_agnostic_core.py"
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".yml",
    ".yaml",
    ".md",
    ".toml",
    ".sql",
    ".rego",
}


def main() -> int:
    framework = re.compile("|".join(FRAMEWORK), re.IGNORECASE)
    product = re.compile("|".join(PRODUCT), re.IGNORECASE)
    failures: list[str] = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == "scripts/check_domain_agnostic.py":
            continue
        if rel.startswith(ALLOW_PREFIXES) or rel in ALLOW_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            if framework.search(line):
                failures.append(f"{rel}:{line_no}: {line.strip()}")
                continue
            if rel.startswith(SCHEMA_PREFIXES) or rel == STAGE0_TEST:
                continue
            if product.search(line):
                failures.append(f"{rel}:{line_no}: {line.strip()}")
    if failures:
        print("core names a domain term:", file=sys.stderr)
        for item in failures:
            print(item, file=sys.stderr)
        return 1
    print(f"domain strip ok ({ROOT})")
    return 0


def _files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


if __name__ == "__main__":
    raise SystemExit(main())
