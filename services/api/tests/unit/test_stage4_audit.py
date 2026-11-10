"""Audit API reads only the hash chain. Proof label: unit (in-process HTTP)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from ar_domain.audit.chain import GENESIS
from ar_domain.audit.read import seal_chain_row
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application

pytestmark = pytest.mark.unit


def _client() -> TestClient:
    app = demo_application()
    principal = Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=demo_id("tenant"),
        permissions=PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email="admin@dev.local",
        display_name="admin",
        roles=frozenset({"tenant_admin"}),
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    return TestClient(app)


def test_unchained_rows_are_hidden_and_a_tampered_row_is_detected() -> None:
    client = _client()
    tenant = str(demo_id("tenant"))
    first = seal_chain_row(
        seq=1, prev_hash=GENESIS, action="auth.login", tenant_id=tenant, actor_id="admin"
    )
    second = seal_chain_row(
        seq=2,
        prev_hash=str(first["hash"]),
        action="auth.logout",
        tenant_id=tenant,
        actor_id="admin",
    )
    other = seal_chain_row(
        seq=1,
        prev_hash=GENESIS,
        action="tenant.updated",
        tenant_id=str(uuid.uuid4()),
        actor_id="other",
    )
    other["id"] = 99
    client.app.state.audit_api.events = [
        first,
        second,
        other,
        {"id": 7, "action": "memory.created", "tenant_id": tenant, "tenant_seq": 7},
    ]
    client.app.state.chat.audit_log.append(
        {"id": 8, "action": "memory.created", "tenant_id": tenant}
    )
    listed = client.get("/api/v1/audit-events")
    assert listed.status_code == 200
    assert [item["action"] for item in listed.json()["items"]] == ["auth.login", "auth.logout"]
    assert client.get("/api/v1/audit-events/99").status_code == 404
    tampered = dict(second)
    tampered["action"] = "auth.login"
    client.app.state.audit_api.events = [first, tampered]
    report = client.post("/api/v1/audit-events:verify")
    assert report.status_code == 200
    body = report.json()
    assert body["ok"] is False
    assert body["brokenAtSeq"] == 2
    assert body["checked"] == 1
