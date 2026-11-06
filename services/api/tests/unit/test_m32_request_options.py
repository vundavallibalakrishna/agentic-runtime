"""Provider keys inside requestOptions survive a read and a write."""

import uuid

from fastapi.testclient import TestClient

from ar_api.routers.m2 import sse_frame
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application


def _client() -> TestClient:
    app = demo_application()
    principal = Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=demo_id("tenant"),
        permissions=PERMISSION_KEYS,
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Dev Admin",
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    return TestClient(app)


def test_request_options_round_trip_keeps_provider_keys() -> None:
    client = _client()
    provider = client.post(
        "/api/v1/model-providers",
        json={"name": "deep", "kind": "fake", "baseUrl": "http://127.0.0.1:8099/v1"},
    )
    assert provider.status_code == 200, provider.text
    options = {"chat_template_kwargs": {"enable_thinking": False}}
    created = client.post(
        "/api/v1/models",
        json={
            "providerId": provider.json()["id"],
            "name": "qwen",
            "upstreamModel": "Qwen/Qwen3-32B",
            "kind": "chat",
            "requestOptions": options,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["requestOptions"] == options
    listed = client.get("/api/v1/models")
    assert listed.status_code == 200
    match = next(row for row in listed.json()["items"] if row["name"] == "qwen")
    assert match["requestOptions"] == options
    again = client.post(
        "/api/v1/models",
        json={
            "providerId": provider.json()["id"],
            "name": "qwen-again",
            "upstreamModel": "Qwen/Qwen3-32B",
            "kind": "chat",
            "requestOptions": match["requestOptions"],
        },
    )
    assert again.status_code == 200, again.text
    assert again.json()["requestOptions"] == options
    stored = client.app.state.chat.models[uuid.UUID(again.json()["id"])]["request_options"]
    assert stored == options
    assert "chatTemplateKwargs" not in stored


def test_sse_heartbeat_is_a_comment() -> None:
    frame = sse_frame({"type": "heartbeat", "seq": 4, "data": {}})
    assert frame == b": ping\n\n"
    event = sse_frame({"type": "run.completed", "seq": 5, "data": {}})
    assert event.startswith(b"id: 5\nevent: run.completed\ndata: ")
