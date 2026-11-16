#!/usr/bin/env python
"""Isolated-install contract.

A chat turn asks fake-llm to call ``list_files``. The worker posts that call
to mcp-gateway and the run must record a successful tool result. The gateway
must time out dialing a CloudNativePG instance pod, while that same pod IP
accepts a connection from the database itself.
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


def tool_turn(base: str) -> None:
    response = httpx.post(
        f"{base}/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if response.status_code != 200:
        raise SystemExit(f"login failed: {response.status_code} {response.text[:200]}")
    cookie = ""
    csrf = ""
    for raw in response.headers.get_list("set-cookie"):
        pair = raw.split(";", 1)[0]
        if pair.startswith("ar_session="):
            cookie = pair
        elif pair.startswith("ar_csrf="):
            csrf = pair.split("=", 1)[1]
    headers = {"cookie": cookie, "x-csrf-token": csrf}
    started = httpx.post(
        f"{base}/v1/agents/assistant:run",
        json={"text": "/tool list_files {}", "stream": False},
        headers=headers,
        timeout=180,
    )
    if started.status_code != 200:
        raise SystemExit(f"run failed: {started.status_code} {started.text[:400]}")
    body = started.json()
    run_id = str(body.get("id") or body.get("runId") or "")
    if not run_id:
        raise SystemExit(f"run response had no id: {list(body)[:8]}")
    calls = httpx.get(
        f"{base}/api/v1/runs/{run_id}/tool-calls",
        headers=headers,
        timeout=30,
    )
    if calls.status_code != 200:
        raise SystemExit(f"tool calls failed: {calls.status_code} {calls.text[:300]}")
    payload = calls.json()
    rows = (
        payload if isinstance(payload, list) else payload.get("items") or payload.get("calls") or []
    )
    if not rows:
        raise SystemExit(f"the run recorded no tool call: {str(payload)[:300]}")
    failed = [
        row
        for row in rows
        if isinstance(row, dict) and (row.get("isError") is True or row.get("status") == "error")
    ]
    if failed:
        raise SystemExit(f"tool call failed: {str(failed[0])[:300]}")
    print(f"tool call ok run={run_id} calls={len(rows)}", flush=True)


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
    pod = kubectl(
        "-n",
        NAMESPACE,
        "get",
        "pods",
        "-l",
        "cnpg.io/podRole=instance",
        "-o",
        "jsonpath={.items[0].metadata.name}",
    ).strip()
    if not instance or not pod:
        raise SystemExit("no CNPG instance pod")
    positive = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "kubectl",
            "-n",
            NAMESPACE,
            "exec",
            pod,
            "-c",
            "postgres",
            "--",
            "pg_isready",
            "-h",
            instance,
            "-p",
            "5432",
        ],
        check=False,
        text=True,
    )
    if positive.returncode != 0:
        raise SystemExit(
            "an allowed pod could not reach the instance, so the negative check is meaningless"
        )
    program = (
        "import socket, sys\n"
        "sock = socket.socket()\n"
        "sock.settimeout(5)\n"
        "try:\n"
        f"    sock.connect(({instance!r}, 5432))\n"
        "except TimeoutError as exc:\n"
        "    print('instance dial timed out:', exc)\n"
        "    sys.exit(0)\n"
        "else:\n"
        "    sys.exit(1)\n"
    )
    denied = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "kubectl",
            "-n",
            NAMESPACE,
            "exec",
            "deploy/agentic-runtime-mcp-gateway",
            "--",
            "python",
            "-c",
            program,
        ],
        check=False,
        text=True,
    )
    if denied.returncode != 0:
        print(denied.stdout, denied.stderr, flush=True)
        raise SystemExit("mcp-gateway reached a CNPG instance or failed for another reason")


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
        for _ in range(60):
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
        tool_turn("http://127.0.0.1:18080")
        database_edges()
    finally:
        forward.terminate()
    print("airgap isolation contract ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
