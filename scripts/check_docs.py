"""Consistency checks for the 1.0 release surface."""

from __future__ import annotations

import sys
from pathlib import Path

from ar_common.settings import CATALOGUE_ENV

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Fail when the release artefacts drift from the catalogue."""
    values = (ROOT / "deploy/helm/agentic-runtime/values.yaml").read_text(encoding="utf-8")
    missing = sorted(name for name in CATALOGUE_ENV if name not in values)
    problems: list[str] = []
    if missing:
        problems.append("values.yaml missing " + ", ".join(missing))
    chart = (ROOT / "deploy/helm/agentic-runtime/Chart.yaml").read_text(encoding="utf-8")
    if "version: 1.0.0" not in chart:
        problems.append("chart version is not 1.0.0")
    if "1.0.0" not in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
        problems.append("CHANGELOG has no 1.0.0")
    required = (
        "docs/testing/m15-checklist.md",
        "docs/07-ops/dr-drills.md",
        "docs/07-ops/release-1.0.md",
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
