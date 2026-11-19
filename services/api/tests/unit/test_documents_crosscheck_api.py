"""The cross-check endpoint: its result, its permission and a cross-tenant 404."""

import uuid
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.documents.library import DocumentLibrary
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application

if TYPE_CHECKING:
    import pytest

_REPORT = (
    b"# Stock count\n\n## Summary\n\nShelving is graded Amber.\n\n## Shelving\n\nGrade: Red.\n"
)
_ANSWER = (
    '{"findings": [{"statement": "Shelving is Amber in the summary and Red in its section.", '
    '"kind": "summary_mismatch", "quotes": ['
    '{"anchor": "p1-s0", "quote": "Shelving is graded Amber.", "value": "Amber"}, '
    '{"anchor": "p1-s1", "quote": "Grade: Red.", "value": "Red"}]}]}'
)


def _client() -> tuple[TestClient, dict[str, object]]:
    app = demo_application()
    holder: dict[str, object] = {
        "tenant": demo_id("tenant"),
        "permissions": PERMISSION_KEYS,
    }

    async def resolve(_scope: object) -> Principal:
        tenant = holder["tenant"]
        permissions = holder["permissions"]
        assert isinstance(tenant, uuid.UUID)
        assert isinstance(permissions, frozenset)
        return Principal(
            kind="user",
            id=str(demo_id("admin")),
            tenant_id=tenant,
            permissions=permissions,
            team_permissions=frozenset(),
            auth_method="bearer",
            email="admin@dev.local",
            display_name="Dev Admin",
        )

    app.state.resolve_principal = resolve
    return TestClient(app), holder


def _uploaded(client: TestClient) -> str:
    created = client.post(
        "/api/v1/library-documents",
        files={"upload": ("stock.md", _REPORT, "text/markdown")},
    )
    assert created.status_code == 200, created.text
    return str(created.json()["id"])


def test_cross_check_returns_findings_with_anchors(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _holder = _client()
    document_id = _uploaded(client)
    asked: list[str] = []

    def ask(task: str, _evidence: str) -> str:
        asked.append(task)
        return _ANSWER

    monkeypatch.setattr(DocumentLibrary, "_ask", lambda _self, _actor, _alias: ask)
    found = client.post(
        f"/api/v1/library-documents/{document_id}:crosscheck", json={"focus": "grades"}
    )
    assert found.status_code == 200, found.text
    body = found.json()
    assert body["kind"] == "crosscheck"
    assert body["documentId"] == document_id
    assert body["passagesRead"] == 2
    assert [row["anchor"] for row in body["findings"][0]["quotes"]] == ["p1-s0", "p1-s1"]
    assert "Pay most attention to: grades" in asked[0]


def test_cross_check_without_a_model_answer_is_not_a_clean_result() -> None:
    client, _holder = _client()
    document_id = _uploaded(client)
    silent = client.post(f"/api/v1/library-documents/{document_id}:crosscheck", json={})
    assert silent.status_code == 503, silent.text
    assert "was not checked" in silent.json()["detail"]


def test_cross_check_needs_the_chat_permission() -> None:
    client, holder = _client()
    document_id = _uploaded(client)
    holder["permissions"] = frozenset({"agents:read"})
    refused = client.post(f"/api/v1/library-documents/{document_id}:crosscheck", json={})
    assert refused.status_code == 403, refused.text


def test_cross_check_is_a_404_for_another_tenant() -> None:
    client, holder = _client()
    document_id = _uploaded(client)
    holder["tenant"] = uuid.uuid4()
    hidden = client.post(f"/api/v1/library-documents/{document_id}:crosscheck", json={})
    assert hidden.status_code == 404, hidden.text
