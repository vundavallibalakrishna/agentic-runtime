"""Production Compose install smoke.

Waits for /readyz, runs one chat turn against the test model, restarts Temporal and
the runtime worker, and checks the workflow is still there. ``AR_SMOKE_OPA=1`` also
proves the OPA bundle (the install has the OPA feature); ``AR_SMOKE_ONLY=policy`` stops
after the policy proof and one tool call through the gateway.
"""

from __future__ import annotations

import asyncio
import http.cookiejar
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from temporalio.client import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sign_in import password_for  # noqa: E402


class _LoopbackCookies(http.cookiejar.DefaultCookiePolicy):
    """Keep the Secure session cookie on the loopback HTTP install."""

    def return_ok_secure(self, cookie: object, request: object) -> bool:
        del cookie, request
        return True

    def set_ok_secure(self, cookie: object, request: object) -> bool:
        del cookie, request
        return True


def _checked(response: httpx.Response) -> dict[str, object]:
    if response.status_code >= 400:
        raise RuntimeError(
            f"{response.request.method} {response.request.url} -> {response.status_code}"
        )
    body = response.json()
    if not isinstance(body, dict):
        raise TypeError("response was not an object")
    return body


def _wait_ready(url: str, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    last = ""
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{url}/readyz", timeout=5)
        except httpx.HTTPError as exc:
            last = type(exc).__name__
        else:
            if response.status_code == 200 and response.json().get("status") == "ready":
                return
            last = response.text[:200]
        time.sleep(2)
    raise RuntimeError(f"/readyz did not become ready: {last}")


def _wait_run(client: httpx.Client, run_id: str, seconds: float) -> dict[str, object]:
    deadline = time.monotonic() + seconds
    current: dict[str, object] = {}
    while time.monotonic() < deadline:
        current = _checked(client.get(f"/api/v1/runs/{run_id}"))
        if str(current.get("status") or "") not in {"queued", "running"}:
            return current
        time.sleep(2)
    raise RuntimeError(f"run {run_id} did not finish")


def _prove_opa_bundle() -> None:
    """OPA has activated the bundle from the API, and the bundle holds the decision rules.

    A loaded bundle is not enough: an image built without the rule files once served an
    empty policy, OPA activated it, and every tool call was then refused.
    """
    port = os.environ.get("AR_OPA_HOST_PORT", "8181")
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + float(os.environ.get("AR_SMOKE_READY_S", "180"))
    last = ""
    while time.monotonic() < deadline:
        try:
            health = httpx.get(f"{base}/health?bundles", timeout=5)
            asked = httpx.post(
                f"{base}/v1/data/ar/policy/decision", json={"input": {"rules": []}}, timeout=5
            )
        except httpx.HTTPError as exc:
            last = type(exc).__name__
        else:
            result = asked.json().get("result") if asked.status_code == 200 else None
            if health.status_code == 200 and isinstance(result, dict) and result.get("decision"):
                print("opa bundle is loaded and answers a decision")
                return
            last = f"health {health.status_code}, decision {asked.text[:200]}"
        time.sleep(2)
    raise RuntimeError(f"OPA bundle did not load its decision rules: {last}")


def _prove_gateway_hop() -> None:
    """The worker posts a tool call to mcp-gateway on the install network.

    Any answer below 500 means the gateway received the call. Cluster egress
    would have refused the private address before a status existed.
    """
    script = "\n".join(
        [
            "import os, uuid",
            "from ar_common.internal_http import internal_post",
            "base = os.environ.get('AR_MCP_GATEWAY_URL', '').rstrip('/')",
            "if not base:",
            "    raise SystemExit('AR_MCP_GATEWAY_URL is empty')",
            "body = {",
            "    'tenant_id': str(uuid.uuid4()),",
            "    'user_id': str(uuid.uuid4()),",
            "    'tool_version_id': str(uuid.uuid4()),",
            "    'arguments': {},",
            "}",
            "response = internal_post(",
            "    base + '/internal/v1/tool-calls:execute', json=body, timeout=20",
            ")",
            "print(response.status_code)",
            "if response.status_code >= 500:",
            "    raise SystemExit(response.text[:300])",
        ]
    )
    completed = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "compose",
            "-f",
            "compose.yaml",
            "-f",
            "tests/compose/ci-model.yaml",
            "--profile",
            "production",
            "exec",
            "-T",
            "runtime-worker",
            "python",
            "-c",
            script,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    status = completed.stdout.strip().splitlines()[-1]
    print(f"worker tool call reached mcp-gateway ({status})")


def main() -> None:  # noqa: PLR0915
    api = os.environ.get("AR_SMOKE_API", "http://127.0.0.1:8000").rstrip("/")
    temporal_address = os.environ.get("AR_SMOKE_TEMPORAL", "127.0.0.1:7233")
    _wait_ready(api, float(os.environ.get("AR_SMOKE_READY_S", "180")))
    # The core decides policy with the built-in evaluator and has no OPA server. With the
    # OPA feature on, the bundle is proved and then a tool call is decided through it.
    if os.environ.get("AR_SMOKE_OPA") == "1":
        _prove_opa_bundle()
    if os.environ.get("AR_SMOKE_ONLY") == "policy":
        _prove_gateway_hop()
        return
    jar = http.cookiejar.CookieJar(policy=_LoopbackCookies())
    with httpx.Client(base_url=api, timeout=60, cookies=httpx.Cookies(jar)) as client:
        signed = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@dev.local", "password": password_for("admin@dev.local")},
        )
        if signed.status_code != 200 or not client.cookies.get("ar_session"):
            raise RuntimeError(f"sign-in failed: {signed.status_code}")
        # The prod cookie is Secure. This smoke talks to loopback over HTTP, so
        # store the same values without that flag for the rest of the turn.
        session = client.cookies.get("ar_session")
        csrf = client.cookies.get("ar_csrf")
        client.cookies.clear()
        client.cookies.set("ar_session", session or "")
        client.cookies.set("ar_csrf", csrf or "")
        origin = os.environ.get("AR_PUBLIC_URL", "http://localhost:3000").rstrip("/")
        client.headers.update({"origin": origin, "x-csrf-token": csrf or ""})
        listed = _checked(client.get("/api/v1/agents"))
        items = listed.get("items")
        if not isinstance(items, list):
            raise TypeError("agent list was not a list")
        agent = next(
            item for item in items if isinstance(item, dict) and item.get("slug") == "assistant"
        )
        conversation = _checked(
            client.post("/api/v1/conversations", json={"agentId": str(agent["id"])})
        )
        posted = _checked(
            client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={"text": "Reply with one word: pong"},
            )
        )
        run = posted.get("run")
        if not isinstance(run, dict):
            raise TypeError("message did not start a run")
        run_id = str(run["id"])
        finished = _wait_run(client, run_id, 180)
        if finished.get("status") != "completed":
            raise RuntimeError(f"run status {finished.get('status')}")

    _prove_gateway_hop()

    async def _prove() -> tuple[str, str]:
        temporal = await Client.connect(temporal_address)
        before = await temporal.get_workflow_handle(f"run-{run_id}").describe()
        workflow_id = before.id
        system = await Client.connect(temporal_address, namespace="temporal-system")
        system_id = ""
        async for row in system.list_workflows(""):
            system_id = row.id
            break
        if not system_id:
            raise RuntimeError("temporal-system listed no workflow")
        return workflow_id, system_id

    workflow_id, system_id = asyncio.run(_prove())
    print(f"workflow {workflow_id} completed; system workflow {system_id}")
    restart = os.environ.get("AR_SMOKE_RESTART", "1")
    if restart != "1":
        return
    subprocess.run(
        [  # noqa: S607
            "docker",
            "compose",
            "-f",
            "compose.yaml",
            "-f",
            "tests/compose/ci-model.yaml",
            "--profile",
            "production",
            "restart",
            "temporal",
            "runtime-worker",
        ],
        check=True,
    )
    _wait_ready(api, 180)

    async def _after() -> None:
        last = "temporal did not accept a connection"
        for _ in range(30):
            try:
                temporal = await asyncio.wait_for(Client.connect(temporal_address), timeout=3)
                described = await temporal.get_workflow_handle(workflow_id).describe()
                system = await Client.connect(temporal_address, namespace="temporal-system")
                still = await system.get_workflow_handle(system_id).describe()
            except Exception as exc:  # noqa: BLE001 - the server is still opening the port
                last = type(exc).__name__
                await asyncio.sleep(2)
                continue
            if described.id != workflow_id or still.id != system_id:
                raise RuntimeError("workflow disappeared after restart")
            return
        raise RuntimeError(last)

    asyncio.run(_after())
    print("workflow survived the restart")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"compose smoke failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
