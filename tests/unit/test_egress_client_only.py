"""Production code opens HTTP only through the egress client."""

from __future__ import annotations

import re
from pathlib import Path

_ROOTS = (
    Path("libs/ar_common/src"),
    Path("libs/ar_domain/src"),
    Path("libs/ar_contracts/src"),
    Path("services"),
)
_ALLOWED = {Path("libs/ar_common/src/ar_common/egress_http.py")}
_CALL = re.compile(
    r"(?:httpx\.(?:Client|AsyncClient|get|post|request|stream)|"
    r"requests\.(?:get|post|Session))\s*\(|httpx\.(?:get|post)\s*,"
)


def test_raw_http_clients_stay_inside_the_egress_module() -> None:
    offenders: list[str] = []
    for root in _ROOTS:
        for path in root.rglob("*.py"):
            if "tests" in path.parts or path in _ALLOWED:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if _CALL.search(line):
                    offenders.append(f"{path}:{number}: {line.strip()}")
    assert offenders == []
