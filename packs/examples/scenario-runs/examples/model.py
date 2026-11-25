"""Synthetic script for tests. It prints a fixed object. It is not a real model."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    params = json.loads(Path("params.json").read_text(encoding="utf-8"))
    result = {"echo": params.get("label", "synthetic"), "units": 2}
    Path("output.json").write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
