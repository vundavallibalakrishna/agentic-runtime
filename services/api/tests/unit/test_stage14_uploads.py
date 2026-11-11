"""The same bytes uploaded two ways are one library document."""

import uuid

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application

_BYTES = b"The same note, uploaded twice.\n"


def _client() -> TestClient:
    holder = {
        "principal": Principal(
            kind="user",
            id=str(demo_id("admin")),
            tenant_id=demo_id("tenant"),
            permissions=PERMISSION_KEYS,
            team_permissions=frozenset(),
            auth_method="bearer",
            email="admin@dev.local",
            display_name="Admin",
            roles=frozenset({"tenant_admin"}),
        )
    }
    app = demo_application()

    async def resolve(scope: object) -> Principal | None:
        del scope
        return holder["principal"]

    app.state.resolve_principal = resolve
    return TestClient(app)


def test_file_upload_and_agent_upload_share_one_document() -> None:
    client = _client()
    listed = client.get("/api/v1/agents")
    rows = listed.json().get("items") or listed.json().get("data") or []
    agent_id = next(row["id"] for row in rows if row["slug"] == "assistant")
    created = client.post(f"/api/v1/agents/{agent_id}/api-keys", json={"label": "cert"})
    assert created.status_code == 200
    headers = {"Authorization": f"Bearer {created.json()['key']}"}
    first = client.post(
        "/api/v1/files:upload",
        files={"upload": ("note.txt", _BYTES, "text/plain")},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/v1/agents/assistant/files",
        headers=headers,
        files={"upload": ("note.txt", _BYTES, "text/plain")},
        data={"mime_type": "text/plain"},
    )
    assert second.status_code == 200, second.text
    assert first.json()["documentId"]
    assert first.json()["documentId"] == second.json()["documentId"]
    assert first.json()["id"] != second.json()["id"]
    stored = client.app.state.chat.library_documents  # type: ignore[attr-defined]
    hashes = [
        row.get("content_hash")
        for row in stored.values()
        if isinstance(row, dict) and row.get("id") == uuid.UUID(first.json()["documentId"])
    ]
    assert len(hashes) == 1
