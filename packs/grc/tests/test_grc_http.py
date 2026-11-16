"""GRC HTTP routes refuse another tenant's catalogue."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application
from ar_testing.demo_people import DEV_TENANT_ID
from grc_pack import enable, mount


def _principal(tenant_id: uuid.UUID, user_id: uuid.UUID) -> Principal:
    return Principal(
        kind="user",
        id=str(user_id),
        tenant_id=tenant_id,
        permissions=PERMISSION_KEYS | frozenset({"grc.catalogues:manage"}),
        auth_method="api_key",
        email="admin@dev.local",
        display_name="Admin",
        roles=frozenset({"tenant_admin"}),
    )


def test_another_tenant_gets_404() -> None:
    app = demo_application()
    mount(app)
    store = app.state.chat
    owner = uuid.uuid4()
    enable(store, DEV_TENANT_ID, owner=owner)
    who = _principal(DEV_TENANT_ID, owner)
    imported = None

    async def as_owner(_scope: object) -> Principal:
        return who

    app.state.resolve_principal = as_owner
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ext/grc/catalogues",
            json={"name": "House", "csv": "key,title,statement\nD1,Door,Locked.\n"},
        )
        assert created.status_code == 200, created.text
        imported = created.json()["id"]
        other = uuid.uuid4()

        async def as_other(_scope: object) -> Principal:
            return _principal(other, uuid.uuid4())

        app.state.resolve_principal = as_other
        hidden = client.get(f"/api/v1/ext/grc/catalogues/{imported}")
    assert hidden.status_code == 404
