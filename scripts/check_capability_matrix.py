#!/usr/bin/env python
"""Fail when docs/09-plan/capability-matrix.md drifts from the code.

The matrix is generated. CI runs this with no arguments. ``--write`` refreshes
the file after a catalogue change.
"""

from __future__ import annotations

import sys

from ar_domain.proof import matrix_path, render_capability_matrix


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    text = render_capability_matrix()
    path = matrix_path()
    if "--write" in args:
        path.write_text(text, encoding="utf-8")
        sys.stdout.write(f"wrote {path}\n")
        return 0
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    if current != text:
        sys.stderr.write(
            "capability matrix drifted from code; "
            "run: uv run python scripts/check_capability_matrix.py --write\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
