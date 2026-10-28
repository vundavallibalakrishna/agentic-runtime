"""Package a release. Spec: docs/07-ops/ci-cd.md §6."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "deploy" / "helm" / "agentic-runtime"


def git_notes(limit: int = 40) -> str:
    """Recent conventional commits, one per line."""
    result = subprocess.run(  # noqa: S603
        ["git", "log", f"-n{limit}", "--pretty=format:%s"],  # noqa: S607
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def package(destination: Path) -> Path:
    """helm package the umbrella chart."""
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # noqa: S603
        ["helm", "package", str(CHART), "--destination", str(destination)],  # noqa: S607
        check=True,
    )
    charts = sorted(destination.glob("agentic-runtime-*.tgz"))
    if not charts:
        raise RuntimeError("helm package produced no chart")
    return charts[-1]


def checksum(path: Path) -> str:
    """SHA-256 of a packed chart."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return digest


def main(argv: list[str] | None = None) -> None:
    """Dry-run prints the plan. --bundle also packs the chart when helm is present."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--bundle", action="store_true")
    parser.add_argument("--destination", default="")
    args = parser.parse_args(argv)
    notes = git_notes()
    sys.stdout.write("release 1.0.0\n")
    sys.stdout.write(notes + "\n")
    if args.dry_run and not args.bundle:
        sys.stdout.write("dry-run: chart package, sbom and cosign sign skipped\n")
        return
    dest = Path(args.destination) if args.destination else ROOT / "dist"
    packed = package(dest)
    digest = checksum(packed)
    sys.stdout.write(f"packed {packed.name} {digest}\n")


if __name__ == "__main__":
    main()
