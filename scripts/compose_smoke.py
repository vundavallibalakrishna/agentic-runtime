"""Production Compose install smoke.

Waits for /readyz, runs one chat turn against fake-llm, restarts Temporal and
the runtime worker, and checks the workflow is still there.
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


def main() -> None:  # noqa: PLR0915
    api = os.environ.get("AR_SMOKE_API", "http://127.0.0.1:8000").rstrip("/")
    temporal_address = os.environ.get("AR_SMOKE_TEMPORAL", "127.0.0.1:7233")
    _wait_ready(api, float(os.environ.get("AR_SMOKE_READY_S", "180")))
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
        ["docker", "compose", "--profile", "production", "restart", "temporal", "runtime-worker"],  # noqa: S607
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
