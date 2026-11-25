"""A slow tool must not freeze the gateway's event loop.

Label: unit
"""

from __future__ import annotations

import asyncio
import time
import uuid

import httpx
import pytest

from ar_common.internal_auth import internal_headers
from ar_common.offload import blocking
from ar_mcp_gateway.main import create_application

_SECRET = "install-secret"  # noqa: S105
_PATH = "/internal/v1/tool-calls:execute"


@pytest.mark.asyncio
async def test_healthz_answers_while_a_tool_call_is_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AR_INTERNAL_AUTH_SECRET", _SECRET)
    monkeypatch.setenv("AR_ENV", "dev")

    def slow(_store: object, _request: dict[str, object]) -> dict[str, object]:
        blocking(time.sleep, 0.6)
        return {"status": "succeeded", "result_preview": "done"}

    monkeypatch.setattr("ar_mcp_gateway.routes.execute", slow)
    app = create_application()
    transport = httpx.ASGITransport(app=app)
    body = {
        "tenantId": str(uuid.uuid4()),
        "userId": str(uuid.uuid4()),
        "toolVersionId": str(uuid.uuid4()),
        "arguments": {},
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        call = asyncio.create_task(
            client.post(
                _PATH,
                json=body,
                headers=internal_headers(_SECRET, "POST", _PATH),
            )
        )
        await asyncio.sleep(0.05)
        started = time.perf_counter()
        health = await client.get("/healthz")
        other = await client.get("/healthz")
        elapsed = time.perf_counter() - started
        result = await call
    assert health.status_code == 200
    assert other.status_code == 200
    assert health.json()["status"] == "ok"
    assert elapsed < 0.3
    assert result.status_code == 200
    assert result.json()["status"] == "succeeded"
