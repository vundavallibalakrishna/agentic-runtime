#!/usr/bin/env python3
"""Squid external ACL helper. Anything other than a 200 from the manager is a deny."""

import os
import sys
import urllib.parse
import urllib.request


def credentials(parts: list[str]) -> tuple[str, str]:
    """Squid sends ``%LOGIN %note{user} %DST``. The note carries ``id:token``."""
    if len(parts) >= 3:
        login = parts[1] if parts[1] != "-" else parts[0]
        return urllib.parse.unquote(login), urllib.parse.unquote(parts[2])
    if len(parts) >= 2:
        return urllib.parse.unquote(parts[0]), urllib.parse.unquote(parts[1])
    return "", ""


def verdict(login: str, host: str) -> str:
    """OK only when the manager allows this sandbox token to reach the host."""
    base = os.environ.get("AR_SANDBOX_MANAGER_URL", "").rstrip("/")
    if not base or ":" not in login or not host:
        return "ERR"
    sandbox_id, token = login.split(":", 1)
    query = urllib.parse.urlencode({"sandbox_id": sandbox_id, "host": host, "token": token})
    try:
        with urllib.request.urlopen(  # noqa: S310 - the manager URL is operator configuration
            f"{base}/internal/v1/egress/check?{query}", timeout=2
        ) as response:
            return "OK" if response.status == 200 else "ERR"
    except OSError:
        return "ERR"


def main() -> None:
    for line in sys.stdin:
        parts = line.strip().split()
        if len(parts) < 2:
            print("ERR", flush=True)  # noqa: T201 - Squid reads the helper's stdout
            continue
        login, host = credentials(parts)
        print(verdict(login, host), flush=True)  # noqa: T201


if __name__ == "__main__":
    main()
