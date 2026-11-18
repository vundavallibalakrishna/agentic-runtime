"""Consistency checks for the 1.0 release surface."""

from __future__ import annotations

import sys
from pathlib import Path

from ar_common.settings import CATALOGUE_ENV

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Fail when the release artefacts drift from the catalogue."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    missing = sorted(name for name in CATALOGUE_ENV if f"{name}=" not in example)
    problems: list[str] = []
    if missing:
        problems.append(".env.example missing " + ", ".join(missing))
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    if "temporalio/server:1.32.1" not in compose:
        problems.append("compose.yaml is not the Temporal server install")
    if "1.0.0" not in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
        problems.append("CHANGELOG has no 1.0.0")
    required = (
        "docs/testing/m15-checklist.md",
        "docs/07-ops/dr-drills.md",
        "docs/07-ops/release-1.0.md",
        "docs/07-ops/compose.md",
        ".github/workflows/release.yml",
        "deploy/airgap/mirror.sh",
        "deploy/airgap/images.txt",
    )
    problems.extend(f"missing {path}" for path in required if not (ROOT / path).is_file())
    if problems:
        sys.stderr.write("\n".join(problems) + "\n")
        raise SystemExit(1)
    sys.stdout.write(f"docs check ok ({len(CATALOGUE_ENV)} catalogue names)\n")


if __name__ == "__main__":
    main()
