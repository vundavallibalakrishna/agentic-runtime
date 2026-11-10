"""Document library HTTP, including a cross-tenant 404."""

import uuid

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application


def _client() -> tuple[TestClient, dict[str, uuid.UUID]]:
    app = demo_application()
    holder = {"tenant": demo_id("tenant"), "user": demo_id("admin")}

    async def resolve(_scope: object) -> Principal:
        return Principal(
            kind="user",
            id=str(holder["user"]),
            tenant_id=holder["tenant"],
            permissions=PERMISSION_KEYS,
            team_permissions=frozenset(),
            auth_method="bearer",
            email="admin@dev.local",
            display_name="Dev Admin",
        )

    app.state.resolve_principal = resolve
    return TestClient(app), holder


def test_library_upload_and_cross_tenant_404() -> None:
    client, holder = _client()
    created = client.post(
        "/api/v1/library-documents",
        files={
            "upload": ("policy.md", b"# Access\n\nStaff use badges at the door.", "text/markdown")
        },
    )
    assert created.status_code == 200, created.text
    document_id = created.json()["id"]
    assert client.get("/api/v1/library-documents").json()["items"]
    assert client.get(f"/api/v1/library-documents/{document_id}/outline").status_code == 200
    assert client.get(f"/api/v1/library-documents/{document_id}/passages").status_code == 200
    assert client.get(f"/api/v1/library-documents/{document_id}/tables").status_code == 200
    other = client.post(
        "/api/v1/library-documents",
        files={
            "upload": (
                "other.md",
                b"# Travel\n\nTrips need approval from a manager.",
                "text/markdown",
            )
        },
    )
    other_id = other.json()["id"]
    compared = client.post(
        f"/api/v1/library-documents/{document_id}:compare",
        json={"otherDocumentId": other_id},
    )
    assert compared.status_code == 200, compared.text
    checked = client.post(
        f"/api/v1/library-documents/{document_id}:judge",
        json={"statements": ["Staff use badges", "Operate a colony on Mars"]},
    )
    assert checked.status_code == 200, checked.text
    assert checked.json()["rows"][1]["verdict"] == "not_found"
    redacted = client.post(f"/api/v1/library-documents/{document_id}:redact")
    assert redacted.status_code == 200
    rewrite = client.post(
        f"/api/v1/library-documents/{document_id}:rewrite",
        json={"instruction": "rephrase the opening"},
    )
    assert rewrite.status_code == 200, rewrite.text
    rewrite_id = rewrite.json()["id"]
    holder["tenant"] = uuid.uuid4()
    hidden = client.get(f"/api/v1/library-documents/{document_id}")
    assert hidden.status_code == 404
    for path in (
        f"/api/v1/library-documents/{document_id}/passages",
        f"/api/v1/library-documents/{document_id}/outline",
        f"/api/v1/library-documents/{document_id}/tables",
        f"/api/v1/document-checks/{checked.json()['id']}",
        f"/api/v1/document-comparisons/{compared.json()['id']}",
        f"/api/v1/document-rewrites/{rewrite_id}",
    ):
        assert client.get(path).status_code == 404
    assert (
        client.post(
            f"/api/v1/library-documents/{document_id}:compare",
            json={"otherDocumentId": other_id},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/document-rewrites/{rewrite_id}:decide", json={"decision": "reject"}
        ).status_code
        == 404
    )
