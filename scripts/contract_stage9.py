#!/usr/bin/env python
"""Stage 9 kind contract. Proof label: contract (fake-llm, no customer model).

Checks the Helm install has 2 API replicas and 2 workers, then logs in, posts
a chat turn, and resumes ``/v1`` SSE on the surviving API pod after one pod is
deleted.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

import httpx
import orjson

NAMESPACE = "agentic-runtime"
ADMIN_EMAIL = "admin@dev.local"
ADMIN_PASSWORD = "stage9-contract-password"  # noqa: S105 - contract fixture, not a tenant secret


def kubectl(*args: str, input_text: str | None = None) -> str:
    completed = subprocess.run(  # noqa: S603 - kubectl arguments are fixed by this script
        ["kubectl", *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr or completed.stdout)
    return completed.stdout


def replicas(namespace: str, name: str) -> int:
    raw = kubectl(
        "-n",
        namespace,
        "get",
        "deploy",
        name,
        "-o",
        "jsonpath={.spec.replicas}",
    )
    return int(raw)


def wait_ready(namespace: str) -> None:
    deadline = time.time() + 900
    while time.time() < deadline:
        raw = kubectl("-n", namespace, "get", "deploy", "agentic-runtime-api", "-o", "json")
        body = orjson.loads(raw)
        status = body.get("status") or {}
        if int(status.get("readyReplicas") or 0) >= 2:
            return
        time.sleep(5)
    raise SystemExit("api deployment did not reach 2 ready replicas")


def port_forward(namespace: str, target: str, local: int, remote: int) -> subprocess.Popen[str]:
    return subprocess.Popen(  # noqa: S603
        [  # noqa: S607
            "kubectl",
            "-n",
            namespace,
            "port-forward",
            target,
            f"{local}:{remote}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def request(
    method: str,
    url: str,
    *,
    body: object | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
) -> tuple[int, dict[str, str], bytes]:
    response = httpx.request(method, url, json=body, headers=headers, timeout=timeout)
    return response.status_code, dict(response.headers), response.content


def login(base: str) -> tuple[str, str]:
    response = httpx.post(
        f"{base}/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if response.status_code != 200:
        raise SystemExit(f"login failed: {response.status_code}")
    session = ""
    csrf = ""
    for raw in response.headers.get_list("set-cookie"):
        pair = raw.split(";", 1)[0]
        if pair.startswith("ar_session="):
            session = pair
        elif pair.startswith("ar_csrf="):
            csrf = pair.split("=", 1)[1]
    if not session or not csrf:
        raise SystemExit("login did not set a session cookie")
    return session, csrf


def api_pods(namespace: str) -> list[str]:
    raw = kubectl(
        "-n",
        namespace,
        "get",
        "pods",
        "-l",
        "app.kubernetes.io/name=api",
        "-o",
        "jsonpath={.items[*].metadata.name}",
    )
    return [item for item in raw.split() if item]


def _event_url(base: str, slug: str, run_id: str) -> str:
    return f"{base}/v1/agents/{slug}/runs/{run_id}/events"


def _sse_id(base: str, token: str, slug: str, run_id: str) -> str:
    last = ""
    with httpx.stream(
        "GET",
        _event_url(base, slug, run_id),
        headers={"authorization": f"Bearer {token}", "accept": "text/event-stream"},
        timeout=30,
    ) as response:
        for line in response.iter_lines():
            if line.startswith("id:"):
                last = line.split(":", 1)[1].strip()
            if last and line.strip() == "":
                return last
    if not last:
        raise SystemExit("the event stream produced no id")
    return last


def _resume_bearer(base: str, token: str, slug: str, run_id: str, event_id: str) -> None:
    with httpx.stream(
        "GET",
        _event_url(base, slug, run_id),
        headers={
            "authorization": f"Bearer {token}",
            "accept": "text/event-stream",
            "last-event-id": event_id,
        },
        timeout=30,
    ) as response:
        chunk = next(response.iter_bytes(256), b"")
    if not chunk:
        raise SystemExit("resume returned an empty stream")


def main() -> int:  # noqa: PLR0915
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default=os.environ.get("STAGE9_NAMESPACE", NAMESPACE))
    parser.add_argument("--out", default="var/stage9-contract.json")
    args = parser.parse_args()
    namespace = args.namespace
    api = replicas(namespace, "agentic-runtime-api")
    workers = replicas(namespace, "agentic-runtime-runtime-worker")
    if api != 2 or workers != 2:
        raise SystemExit(f"expected 2 api and 2 workers, got {api} and {workers}")
    kubectl("-n", namespace, "get", "sts", "agentic-runtime-postgres")
    kubectl("-n", namespace, "get", "sts", "agentic-runtime-valkey")
    kubectl("-n", namespace, "get", "deploy", "agentic-runtime-mcp-gateway")
    kubectl("-n", namespace, "get", "deploy", "agentic-runtime-sandbox-manager")
    kubectl("-n", namespace, "get", "deploy", "agentic-runtime-temporal")
    wait_ready(namespace)
    forward = port_forward(namespace, "svc/agentic-runtime-api", 18080, 8000)
    try:
        time.sleep(2)
        base = "http://127.0.0.1:18080"
        status, _headers, _body = request("GET", f"{base}/readyz")
        if status != 200:
            raise SystemExit(f"readyz returned {status}")
        cookie, csrf = login(base)
        status, _headers, body = request("GET", f"{base}/api/v1/agents", headers={"cookie": cookie})
        if status != 200:
            raise SystemExit(f"agents list failed: {status} {body[:200]!r}")
        agents = orjson.loads(body)
        rows = (
            agents
            if isinstance(agents, list)
            else agents.get("items") or agents.get("agents") or []
        )
        assistant = next(
            (row for row in rows if isinstance(row, dict) and row.get("slug") == "assistant"),
            None,
        )
        if not isinstance(assistant, dict):
            raise SystemExit("the tenant has no assistant agent")
        agent_id = str(assistant.get("id"))
        status, _headers, body = request(
            "POST",
            f"{base}/api/v1/agents/{agent_id}/api-keys",
            body={"label": "stage9", "scope": "agent"},
            headers={"cookie": cookie, "x-csrf-token": csrf},
        )
        if status not in {200, 201}:
            raise SystemExit(f"api key failed: {status} {body[:300]!r}")
        created = orjson.loads(body)
        token = str(created.get("key") or created.get("secret") or "")
        if not token:
            raise SystemExit("api key response had no secret")
        auth = {"authorization": f"Bearer {token}"}
        status, _headers, body = request(
            "POST",
            f"{base}/v1/agents/assistant:run",
            body={"text": "Reply with the single word pong.", "stream": False},
            headers=auth,
            timeout=120,
        )
        if status != 200:
            raise SystemExit(f"run failed: {status} {body[:300]!r}")
        reply = orjson.loads(body)
        run_id = str(reply.get("id") or reply.get("runId") or "")
        if not run_id:
            raise SystemExit(f"run response had no id: {list(reply)[:8]}")
        pods = api_pods(namespace)
        if len(pods) < 2:
            raise SystemExit(f"expected two api pods, saw {pods}")
        event_id = _sse_id(base, token, "assistant", run_id)
        killed = pods[0]
        kubectl("-n", namespace, "delete", "pod", killed, "--wait=false")
        _resume_bearer(base, token, "assistant", run_id, event_id)
        score = {
            "label": "contract",
            "apiReplicas": api,
            "workerReplicas": workers,
            "login": "ok",
            "model": "fake-llm",
            "sse": "resumed",
            "killedPod": killed,
            "runId": run_id,
        }
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = orjson.dumps(score, option=orjson.OPT_INDENT_2).decode() + "\n"
        path.write_text(rendered, encoding="utf-8")
        print(orjson.dumps(score).decode())
    finally:
        forward.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
