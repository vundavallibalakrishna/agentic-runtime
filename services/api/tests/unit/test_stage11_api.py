"""HTTP coverage for the stage 11 routes: reset, summary, resume, and push."""

import uuid

from fastapi.testclient import TestClient

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


def test_summary_resume_and_push_subscription() -> None:
    client = _client()
    created = client.post("/api/v1/conversations", json={})
    assert created.status_code == 200
    conversation_id = created.json()["id"]
    summary = client.get(f"/api/v1/conversations/{conversation_id}/summary")
    assert summary.status_code == 200
    assert summary.json()["conversationId"] == conversation_id
    refreshed = client.post(f"/api/v1/conversations/{conversation_id}/summary:refresh")
    assert refreshed.status_code == 200
    run_id = uuid.uuid4()
    client.app.state.chat.runs[run_id] = {
        "id": run_id,
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("admin"),
        "status": "failed",
        "conversation_id": uuid.UUID(conversation_id),
        "checkpoint": {"worker_loop": {"step": 1}},
    }
    resumed = client.post(f"/api/v1/runs/{run_id}:resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"
    subscribed = client.post(
        "/api/v1/notifications/push-subscriptions",
        json={"endpoint": "https://push.example/sub", "contentEncoding": "aes128gcm"},
    )
    assert subscribed.status_code == 200
    removed = client.delete(f"/api/v1/notifications/push-subscriptions/{subscribed.json()['id']}")
    assert removed.status_code == 200
    missing = client.delete(f"/api/v1/notifications/push-subscriptions/{uuid.uuid4()}")
    assert missing.status_code == 404


def test_password_reset_accepts_a_known_address_and_stays_silent() -> None:
    client = TestClient(demo_application())
    known = client.post("/api/v1/auth/password-reset", json={"email": "admin@dev.local"})
    assert known.status_code == 200
    assert known.json()["accepted"] is True
    silent = client.post("/api/v1/auth/password-reset", json={})
    assert silent.json()["accepted"] is True
    outbox = getattr(client.app.state.chat, "outbox", None) or []
    assert outbox
    confirmed = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": outbox[-1]["body"], "password": "new-password-1"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["reset"] is True
