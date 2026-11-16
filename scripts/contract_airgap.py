#!/usr/bin/env python
"""Isolated-install contract.

A chat turn asks fake-llm to call ``general.list_files``. The worker posts that call
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


def _session(response: httpx.Response) -> dict[str, str]:
    cookie = ""
    csrf = ""
    for raw in response.headers.get_list("set-cookie"):
        pair = raw.split(";", 1)[0]
        if pair.startswith("ar_session="):
            cookie = pair
        elif pair.startswith("ar_csrf="):
            csrf = pair.split("=", 1)[1]
    return {"cookie": cookie, "x-csrf-token": csrf}


def _assistant_id(base: str, headers: dict[str, str]) -> str:
    agents = httpx.get(f"{base}/api/v1/agents", headers=headers, timeout=30)
    if agents.status_code != 200:
        raise SystemExit(f"agents list failed: {agents.status_code} {agents.text[:200]}")
    listed = agents.json()
    rows = listed if isinstance(listed, list) else listed.get("items") or listed.get("agents") or []
    assistant = next(
        (row for row in rows if isinstance(row, dict) and row.get("slug") == "assistant"),
        None,
    )
    if not isinstance(assistant, dict):
        raise SystemExit("the tenant has no assistant agent")
    return str(assistant["id"])


def _sql(statement: str) -> str:
    """Read Postgres directly. A second API replica does not see the writer's memory."""
    pod = kubectl(
        "-n",
        NAMESPACE,
        "get",
        "pods",
        "-l",
        "cnpg.io/podRole=instance,cnpg.io/instanceRole=primary",
        "-o",
        "jsonpath={.items[0].metadata.name}",
    ).strip()
    if not pod:
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
    return kubectl(
        "-n",
        NAMESPACE,
        "exec",
        pod,
        "-c",
        "postgres",
        "--",
        "psql",
        "-d",
        "ar",
        "-tA",
        "-c",
        statement,
    )


def tool_turn(base: str) -> None:
    response = httpx.post(
        f"{base}/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if response.status_code != 200:
        raise SystemExit(f"login failed: {response.status_code} {response.text[:200]}")
    headers = _session(response)
    opened = httpx.post(
        f"{base}/api/v1/conversations",
        json={"agentId": _assistant_id(base, headers)},
        headers=headers,
        timeout=30,
    )
    if opened.status_code not in {200, 201}:
        raise SystemExit(f"conversation failed: {opened.status_code} {opened.text[:300]}")
    conversation_id = str(opened.json().get("id") or "")
    posted = httpx.post(
        f"{base}/api/v1/conversations/{conversation_id}/messages",
        json={"text": "/tool general__list_files {}"},
        headers=headers,
        timeout=30,
    )
    if posted.status_code not in {200, 202}:
        raise SystemExit(f"message failed: {posted.status_code} {posted.text[:300]}")
    run = posted.json().get("run") if isinstance(posted.json().get("run"), dict) else {}
    run_id = str(run.get("id") or "")
    if not run_id or any(char not in "0123456789abcdef-" for char in run_id.lower()):
        raise SystemExit(f"message response had no run id: {list(posted.json())[:8]}")
    # The chat route starts the Temporal workflow. The worker writes tool_calls.
    for _ in range(45):
        recorded = _sql(
            "SELECT status || '|' || is_error::text FROM tool_calls "  # noqa: S608
            f"WHERE run_id = '{run_id}'"
        ).strip()
        if recorded:
            status, _, flag = recorded.splitlines()[0].partition("|")
            if flag in {"t", "true"} or status in {"failed", "denied", "rejected"}:
                raise SystemExit(f"tool call failed: {recorded.splitlines()[0]}")
            if status == "succeeded":
                print(f"tool call ok run={run_id}", flush=True)
                return
        time.sleep(2)
    state = _sql(f"SELECT status FROM runs WHERE id = '{run_id}'").strip()  # noqa: S608
    raise SystemExit(f"the run recorded no tool call: run={run_id} status={state}")


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
