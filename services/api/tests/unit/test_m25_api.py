"""Knowledge member and skill import HTTP, including a cross-tenant 404."""

import uuid

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application
from ar_testing.stand_in import EMBEDDING_MODEL


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


def test_member_search_and_skill_import() -> None:
    client, holder = _client()
    uploaded = client.post(
        "/api/v1/library-documents",
        files={
            "upload": (
                "dock.md",
                b"# Dock\n\nThe north dock code is ND-1844-QUILL.\n",
                "text/markdown",
            )
        },
    )
    assert uploaded.status_code == 200
    library_id = uploaded.json()["id"]
    created = client.post(
        "/api/v1/knowledge/collections",
        json={"name": "Docks", "slug": "docks", "description": "Dock codes"},
    )
    assert created.status_code == 200
    collection_id = created.json()["id"]
    assert created.json()["embeddingModel"] == EMBEDDING_MODEL
    assert created.json()["dims"] == 1024
    added = client.post(
        f"/api/v1/knowledge/collections/{collection_id}/members",
        json={"kind": "library", "libraryDocumentId": library_id},
    )
    assert added.status_code == 200
    assert added.json()["result"] == "indexed"
    found = client.post(
        "/api/v1/knowledge/search",
        json={"query": "north dock code", "collectionIds": [collection_id]},
    )
    assert found.status_code == 200
    assert found.json()["hits"]
    holder["tenant"] = uuid.uuid4()
    hidden = client.get(f"/api/v1/knowledge/collections/{collection_id}")
    assert hidden.status_code == 404
    holder["tenant"] = demo_id("tenant")
    imported = client.post(
        "/api/v1/skills:import",
        json={
            "markdown": (
                "---\nname: Weekly status\nslug: weekly-status\n"
                "description: Use when asked for a weekly status note.\n---\n\n"
                "Begin with STATUS-OK.\n"
            )
        },
    )
    assert imported.status_code == 200
    skill_id = imported.json()["id"]
    exported = client.post(f"/api/v1/skills/{skill_id}:export")
    assert exported.status_code == 200
    assert "STATUS-OK" in exported.json()["markdown"]
    holder["tenant"] = uuid.uuid4()
    assert client.post(f"/api/v1/skills/{skill_id}:export").status_code == 404
