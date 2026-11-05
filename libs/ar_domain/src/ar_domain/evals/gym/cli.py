"""CLI for the tool-choice gym. Printing stays in the script wrapper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ar_domain.evals.gym.live import LIVE_FLAG, LIVE_KEY, LiveConfigError, live_requested
from ar_domain.evals.gym.runner import run_suite
from ar_domain.evals.gym.score import render_scorecard


def main(argv: list[str] | None = None) -> int:
    """Run the gym. Exit 2 when live mode is on and the cert key is missing."""
    parser = argparse.ArgumentParser(prog="ar_domain.evals.gym")
    parser.add_argument(
        "--live",
        action="store_true",
        help=f"Call the cert model. Requires {LIVE_FLAG}=1 and {LIVE_KEY}.",
    )
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        help="Scorecard path. Defaults to the committed dry-run file, or the live file.",
    )
    args = parser.parse_args(argv)
    live = bool(args.live) or live_requested()
    if live and not live_requested():
        sys.stderr.write(f"refusing live run without {LIVE_FLAG}=1\n")
        return 2
    try:
        report = run_suite(live=live)
    except LiveConfigError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    path = args.write if isinstance(args.write, Path) else _default_path(live=live)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_scorecard(report), encoding="utf-8")
    sys.stdout.write(
        f"{report.mode} {report.passed_count}/{report.total} ({report.percent}%) -> {path}\n"
    )
    return 0 if report.passed_count == report.total else 1


def _default_path(*, live: bool) -> Path:
    root = _repo_root()
    if live:
        return root / "docs" / "testing" / "eval-gym" / "live-scorecard.md"
    return root / "docs" / "testing" / "m33c-scorecard.md"


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docs" / "testing" / "eval-gym" / "tasks.yaml").is_file():
            return parent
    return Path.cwd()
