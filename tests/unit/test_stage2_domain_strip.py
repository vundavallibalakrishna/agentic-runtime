"""Stage 2: core stays free of industry terms."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.unit
def test_core_passes_the_domain_grep() -> None:
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(  # noqa: S603
        [sys.executable, str(root / "scripts" / "check_domain_agnostic.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
