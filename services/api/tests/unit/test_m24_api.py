"""Document library HTTP, including a cross-tenant 404."""

import asyncio
import time
import uuid
from collections.abc import Awaitable
from typing import TYPE_CHECKING

import httpx
from fastapi.testclient import TestClient

from ar_common.offload import blocking
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.documents.library import DocumentLibrary
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application

if TYPE_CHECKING:
    import pytest


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
    assert compared.status_code in {404, 405}, compared.text
    checked = client.post(
        f"/api/v1/library-documents/{document_id}:judge",
        json={"statements": ["Staff use badges", "Operate a colony on Mars"]},
    )
    assert checked.status_code in {404, 405}, checked.text
    redacted = client.post(f"/api/v1/library-documents/{document_id}:redact")
    assert redacted.status_code in {404, 405}
    rewrite = client.post(
        f"/api/v1/library-documents/{document_id}:rewrite",
        json={"instruction": "rephrase the opening"},
    )
    assert rewrite.status_code in {404, 405}, rewrite.text
    rewrite_id = None
    holder["tenant"] = uuid.uuid4()
    hidden = client.get(f"/api/v1/library-documents/{document_id}")
    assert hidden.status_code == 404
    for path in (
        f"/api/v1/library-documents/{document_id}/passages",
        f"/api/v1/library-documents/{document_id}/outline",
        f"/api/v1/library-documents/{document_id}/tables",
    ):
        assert client.get(path).status_code == 404
    del checked, compared, rewrite_id
    assert client.post(
        f"/api/v1/library-documents/{document_id}:compare",
        json={"otherDocumentId": other_id},
    ).status_code in {404, 405}
    assert client.post(
        "/api/v1/document-rewrites/00000000-0000-0000-0000-000000000000:decide",
        json={"decision": "reject"},
    ).status_code in {404, 405}


def _upload(client: TestClient, name: str, body: bytes) -> str:
    made = client.post("/api/v1/library-documents", files={"upload": (name, body, "text/markdown")})
    assert made.status_code == 200, made.text
    return str(made.json()["id"])


def test_two_documents_are_compared_without_a_model_and_another_tenant_gets_404() -> None:
    client, holder = _client()
    same = "## Access\n\nStaff use badges at every door.\n\n"
    old = _upload(
        client,
        "policy-v1.md",
        (
            f"# Policy\n\n{same}## Logs\n\nLogs are kept for 90 days.\n\n"
            "## Media\n\nUSB sticks need approval.\n"
        ).encode(),
    )
    new = _upload(
        client,
        "policy-v2.md",
        (
            f"# Policy\n\n{same}## Logs\n\nLogs are kept for 365 days.\n\n"
            "## AI\n\nAI systems are registered.\n"
        ).encode(),
    )
    found = client.get(f"/api/v1/library-documents/{old}/diff", params={"otherDocumentId": new})
    assert found.status_code == 200, found.text
    body = found.json()
    assert body["left"]["id"] == old
    assert body["right"]["id"] == new
    by_status: dict[str, list[dict[str, str]]] = {}
    for section in body["sections"]:
        by_status.setdefault(section["status"], []).append(section)
    [changed] = [row for row in by_status["changed"] if "90 days" in row["leftQuote"]]
    assert "365 days" in changed["rightQuote"]
    assert any("USB sticks" in row["leftQuote"] for row in by_status["removed"])
    assert any("AI systems" in row["rightQuote"] for row in by_status["added"])
    # The section that is the same in both is counted and not listed.
    assert body["counts"] == {"changed": 1, "added": 1, "removed": 1, "unchanged": 1}
    assert not any("badges" in str(row) for row in body["sections"])
    # The other document is required, and must be one the caller can see.
    assert client.get(f"/api/v1/library-documents/{old}/diff").status_code == 422
    missing = client.get(
        f"/api/v1/library-documents/{old}/diff", params={"otherDocumentId": str(uuid.uuid4())}
    )
    assert missing.status_code == 404
    holder["tenant"] = uuid.uuid4()
    hidden = client.get(f"/api/v1/library-documents/{old}/diff", params={"otherDocumentId": new})
    assert hidden.status_code == 404


def test_rule_set_import_is_hidden_from_another_tenant() -> None:
    client, holder = _client()
    created = client.post(
        "/api/v1/rule-sets",
        json={
            "id": "door-access",
            "version": "1",
            "items": [{"itemId": "badges", "statement": "Staff use badges at the door."}],
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["id"] == "door-access"
    holder["tenant"] = uuid.uuid4()
    hidden = client.get("/api/v1/rule-sets/door-access", params={"version": "1"})
    assert hidden.status_code == 404


def test_a_document_check_waiting_on_a_model_does_not_hold_up_other_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 14: the API answered nothing for half a minute while one check ran."""
    client, _holder = _client()
    created = client.post(
        "/api/v1/library-documents",
        files={"upload": ("policy.md", b"# Access\n\nOwner: Security.", "text/markdown")},
    )
    document_id = created.json()["id"]
    app = client.app

    def slow_model(_self: object, _actor: object, _alias: str) -> object:
        def ask(_system: str, _evidence: str) -> str:
            blocking(time.sleep, 0.6)
            return "{}"

        return ask

    monkeypatch.setattr(DocumentLibrary, "_ask", slow_model)

    async def both() -> tuple[float, float]:
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://api") as http:
            started = time.monotonic()

            async def timed(call: Awaitable[httpx.Response]) -> float:
                response = await call
                assert response.status_code == 200, response.text
                return time.monotonic() - started

            slow = asyncio.create_task(timed(http.get("/api/v1/library-documents")))
            await asyncio.sleep(0.05)
            quick = await timed(http.get(f"/api/v1/library-documents/{document_id}"))
            return quick, await slow

    quick, slow = asyncio.run(both())
    assert quick < 1
    assert slow < 1
