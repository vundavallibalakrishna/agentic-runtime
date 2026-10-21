"""Bind the default local ports so AUTO_PORTS has to move them.

The fresh-clone CI job starts this, runs ``make ports-check AUTO_PORTS=1``,
and leaves the sockets open until the second ports check. A port that is
already taken counts as held.

The listening sockets have to stay referenced for the whole process. CPython
closes an unreferenced socket as soon as ``hold`` returns, and the port is
free again before ``ports-check`` runs.
"""

import socket
import time

DEFAULTS = (5432, 6379, 7233, 8000, 8001, 8013)

# Process-lifetime references. ``main`` must not drop what ``hold`` returns.
_HELD: list[socket.socket] = []


def hold(ports: tuple[int, ...] = DEFAULTS) -> list[socket.socket]:
    """Listen on each port that is still free."""
    opened: list[socket.socket] = []
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            print(f"hold {port}: already taken ({exc})", flush=True)
            sock.close()
            continue
        sock.listen(1)
        opened.append(sock)
        print(f"holding {port}", flush=True)
    return opened


def main() -> None:
    """Hold the default ports until the process is killed.

    An empty result still sleeps. Every default can already be taken, and
    exiting would look like the holder died before ``ports-check``.
    """
    _HELD.extend(hold())
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
