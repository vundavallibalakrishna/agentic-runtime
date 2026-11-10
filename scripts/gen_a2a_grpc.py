#!/usr/bin/env python
"""Generate the A2A gRPC stubs. ``make gen`` runs this. Do not edit the output."""

from __future__ import annotations

import sys
from pathlib import Path

from grpc_tools import protoc

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "contracts" / "a2a" / "a2a.proto"
OUT = ROOT / "libs" / "ar_domain" / "src" / "ar_domain" / "exposure" / "a2a_gen"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    init = OUT / "__init__.py"
    if not init.is_file():
        init.write_text(
            '"""Generated A2A stubs. Regenerate with scripts/gen_a2a_grpc.py."""\n',
            encoding="utf-8",
        )
    code = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{PROTO.parent}",
            f"--python_out={OUT}",
            f"--grpc_python_out={OUT}",
            str(PROTO),
        ]
    )
    if code != 0:
        return code
    grpc = OUT / "a2a_pb2_grpc.py"
    text = grpc.read_text(encoding="utf-8")
    text = text.replace(
        "import a2a_pb2 as a2a__pb2",
        "from ar_domain.exposure.a2a_gen import a2a_pb2 as a2a__pb2",
    )
    grpc.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
