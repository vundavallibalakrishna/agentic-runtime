"""The docker driver starts an ar-sandbox container and the agent runs in it. Task: M40-T01c.

A canary, not a unit-job dependency: it needs a docker daemon and the ``ar-sandbox`` image,
and skips when either is missing (OQ-37).
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from ar_sandbox_manager.drivers.docker import (
    docker_available,
    image_present,
    start_sandbox,
    stop_sandbox,
)

pytestmark = pytest.mark.integration

IMAGE = "ar-sandbox:dev"


async def test_driver_starts_the_agent_and_runs_a_command() -> None:
    if not docker_available() or not await image_present(IMAGE):
        pytest.skip("docker daemon and the ar-sandbox image are required")
    name = f"ar-sbx-test-{uuid.uuid4().hex[:8]}"
    info = await start_sandbox(IMAGE, name, token="canary")  # noqa: S106 - a test credential
    headers = {"Authorization": "Bearer canary"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            health = await client.get(f"{info['endpoint_url']}/healthz", headers=headers)
            assert health.status_code == 200
            ran = await client.post(
                f"{info['endpoint_url']}/mcp",
                headers=headers,
                json={
                    "name": "sandbox.exec",
                    "arguments": {"command": "echo driver-ok > r.txt; cat r.txt"},
                },
            )
            body = ran.json()
            assert body["structured"]["exit_code"] == 0
            assert "driver-ok" in body["structured"]["stdout"]
            assert any("r.txt" in name for name in body["structured"]["new_files"])
            # The token is enforced: a call without it is rejected.
            denied = await client.post(
                f"{info['endpoint_url']}/mcp",
                json={"name": "sandbox.exec", "arguments": {"command": "echo hi"}},
            )
            assert denied.status_code == 401
    finally:
        await stop_sandbox(str(info["container_id"]))
