#!/usr/bin/env python3
"""Basic-auth helper. Squid only fills %LOGIN after a scheme is configured.

The sandbox proxy URL is ``http://sbx-<sandbox_id>:<token>@squid:3128``.
%LOGIN is the username alone, so this rewrites it to ``<sandbox_id>:<token>``
for the external ACL helper.
"""

import sys


def rewrite(line: str) -> str:
    """Turn ``username password`` into the login the egress helper expects."""
    parts = line.strip().split(" ", 1)
    if len(parts) < 2 or not parts[0] or not parts[1].strip():
        return "ERR"
    user, password = parts[0], parts[1].strip()
    if user.startswith("sbx-"):
        user = user[4:]
    login = user if ":" in user else f"{user}:{password}"
    return f"OK user={login}"


def main() -> None:
    for line in sys.stdin:
        print(rewrite(line), flush=True)  # noqa: T201 - Squid reads the helper's stdout


if __name__ == "__main__":
    main()
