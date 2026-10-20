"""Fail if .env.example omits a variable from the environment catalogue."""

import re
import sys
from pathlib import Path

from ar_common.settings import CATALOGUE_ENV

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"
ASSIGN = re.compile(r"^([A-Z][A-Z0-9_]*)=")


def main() -> None:
    found = {
        match.group(1)
        for line in EXAMPLE.read_text(encoding="utf-8").splitlines()
        if (match := ASSIGN.match(line.strip()))
    }
    missing = sorted(CATALOGUE_ENV - found)
    extra = sorted(name for name in found if name.startswith("AR_") and name not in CATALOGUE_ENV)
    if missing or extra:
        if missing:
            print("missing from .env.example:", ", ".join(missing), file=sys.stderr)
        if extra:
            print("not in catalogue:", ", ".join(extra), file=sys.stderr)
        raise SystemExit(1)
    print(f"{len(found)} catalogue variables listed")


if __name__ == "__main__":
    main()
