"""The docker driver starts an ar-sandbox container and the agent runs in it. Task: M40-T01c.

A canary, not a unit-job dependency: it needs a docker daemon and the ``ar-sandbox`` image,
and skips when either is missing (OQ-37).
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest

from ar_sandbox_manager.drivers.docker import docker_available, start_sandbox, stop_sandbox

pytestmark = pytest.mark.integration

IMAGE = "ar-sandbox:dev"


async def _image_present() -> bool:
    import aiodocker

    docker: Any = aiodocker.Docker()
    try:
        await docker.images.inspect(IMAGE)
    except Exception:  # noqa: BLE001 - a missing image or daemon means skip
        return False
    else:
        return True
    finally:
        await docker.close()


async def test_driver_starts_the_agent_and_runs_a_command() -> None:
    if not docker_available() or not await _image_present():
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
