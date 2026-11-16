#!/usr/bin/env python
"""Isolated-install contract. Proof: one tool hop and a denied instance dial.

The API run shows API to Temporal to the worker. The worker then posts to the
gateway's tool endpoint. The gateway must not open a TCP connection to a
CloudNativePG instance pod on 5432, and must open one to the pooler.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import httpx

NAMESPACE = os.environ.get("AIRGAP_NAMESPACE", "agentic-runtime")
ADMIN_EMAIL = "admin@dev.local"
ADMIN_PASSWORD = "stage9-contract-password"  # noqa: S105 - contract fixture, not a tenant secret


def kubectl(*args: str) -> str:
    completed = subprocess.run(  # noqa: S603
        ["kubectl", *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr or completed.stdout)
    return completed.stdout


def exec_python(deploy: str, program: str) -> None:
    completed = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "kubectl",
            "-n",
            NAMESPACE,
            "exec",
            f"deploy/{deploy}",
            "--",
            "python",
            "-c",
            program,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(completed.stdout, completed.stderr, flush=True)
        raise SystemExit(f"{deploy} check failed: {completed.returncode}")


def tool_hop(base: str) -> None:
    response = httpx.post(
        f"{base}/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if response.status_code != 200:
        raise SystemExit(f"login failed: {response.status_code}")
    cookie = ""
    for raw in response.headers.get_list("set-cookie"):
        pair = raw.split(";", 1)[0]
        if pair.startswith("ar_session="):
            cookie = pair
    if not cookie:
        raise SystemExit("login did not set a session cookie")
    agents = httpx.get(f"{base}/api/v1/agents", headers={"cookie": cookie}, timeout=30)
    if agents.status_code != 200:
        raise SystemExit(f"agents list failed: {agents.status_code}")
    # The worker posts to the gateway. A validation error still proves the socket.
    program = (
        "import os, sys, urllib.error, urllib.request\n"
        "url = os.environ['AR_MCP_GATEWAY_URL'].rstrip('/') + '/internal/v1/tool-calls:execute'\n"
        "req = urllib.request.Request(url, data=b'{}', "
        "headers={'content-type': 'application/json'}, method='POST')\n"
        "try:\n"
        "    urllib.request.urlopen(req, timeout=10)\n"
        "except urllib.error.HTTPError as exc:\n"
        "    sys.exit(0 if exc.code in {400, 422} else 1)\n"
        "except Exception:\n"
        "    sys.exit(1)\n"
        "sys.exit(0)\n"
    )
    exec_python("agentic-runtime-runtime-worker", program)


def database_edges() -> None:
    instance = kubectl(
        "-n",
        NAMESPACE,
        "get",
        "pods",
        "-l",
        "cnpg.io/podRole=instance",
        "-o",
        "jsonpath={.items[0].status.podIP}",
    ).strip()
    if not instance:
        raise SystemExit("no CNPG instance pod IP")
    wrapper = (
        "import socket, sys\n"
        "try:\n"
        f"    sock = socket.create_connection(({instance!r}, 5432), timeout=5)\n"
        "except OSError:\n"
        "    sys.exit(0)\n"
        "sock.close()\n"
        "sys.exit(1)\n"
    )
    exec_python("agentic-runtime-mcp-gateway", wrapper)
    pooler = (
        "import socket, sys\n"
        "sock = socket.create_connection(('agentic-runtime-pg-pooler', 5432), timeout=5)\n"
        "sock.close()\n"
    )
    exec_python("agentic-runtime-mcp-gateway", pooler)


def main() -> int:
    forward = subprocess.Popen(  # noqa: S603
        [  # noqa: S607
            "kubectl",
            "-n",
            NAMESPACE,
            "port-forward",
            "deploy/agentic-runtime-api",
            "18080:8000",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ready = False
        for _ in range(30):
            try:
                response = httpx.get("http://127.0.0.1:18080/readyz", timeout=2)
            except httpx.HTTPError:
                time.sleep(1)
                continue
            if response.status_code == 200:
                ready = True
                break
        if not ready:
            raise SystemExit("api /readyz did not answer")
        tool_hop("http://127.0.0.1:18080")
        database_edges()
    finally:
        forward.terminate()
    print("airgap isolation contract ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
