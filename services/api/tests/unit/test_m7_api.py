"""Knowledge HTTP surface, including the cross-tenant 404."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _client(
    *,
    tenant: uuid.UUID | None = None,
    user: str = "admin",
    permissions: frozenset[str] = PERMISSION_KEYS,
    roles: frozenset[str] = frozenset({"tenant_admin"}),
) -> TestClient:
    app = create_application()
    principal = Principal(
        kind="user",
        id=str(demo_id(user)),
        tenant_id=tenant or demo_id("tenant"),
        permissions=permissions,
        team_permissions=frozenset(),
        auth_method="bearer",
        email=f"{user}@dev.local",
        display_name=user,
        roles=roles,
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    return TestClient(app)


def test_library_search_is_scoped_and_cross_tenant_is_404() -> None:
    admin = _client()
    listed = admin.get("/api/v1/knowledge/collections")
    assert listed.status_code == 200
    library = next(item for item in listed.json()["items"] if item["slug"] == "company-library")
    collection_id = library["id"]
    payroll = admin.post(
        "/api/v1/knowledge/search",
        json={
            "query": "When is payroll released?",
            "collectionIds": [collection_id],
            "debug": True,
        },
    )
    assert payroll.status_code == 200
    body = payroll.json()
    assert body["debug"]["backend"] == "memory"
    assert any(hit["title"] == "Payroll calendar" for hit in body["hits"])
    member = _client(
        user="member",
        permissions=frozenset({"knowledge:read"}),
        roles=frozenset({"member"}),
    )
    hidden = member.post(
        "/api/v1/knowledge/search",
        json={"query": "When is payroll released?", "collectionIds": [collection_id]},
    )
    assert hidden.status_code == 200
    assert all(hit["title"] != "Payroll calendar" for hit in hidden.json()["hits"])
    denied = member.post(
        "/api/v1/knowledge/collections",
        json={"slug": "secret", "name": "Secret"},
    )
    assert denied.status_code == 403
    outsider = _client(tenant=uuid.uuid4())
    missing = outsider.get(f"/api/v1/knowledge/collections/{collection_id}")
    assert missing.status_code == 404
    created = admin.post(
        "/api/v1/knowledge/collections",
        json={"slug": "notes", "name": "Notes", "description": "Scratch"},
    )
    assert created.status_code == 200
    assert created.json()["slug"] == "notes"
    bad = admin.post(
        "/api/v1/knowledge/collections",
        json={"slug": "wide", "name": "Wide", "dims": 12},
    )
    assert bad.status_code == 422


def test_collection_routes_cover_sources_documents_and_jobs() -> None:
    admin = _client()
    created = admin.post(
        "/api/v1/knowledge/collections",
        json={"slug": "routes", "name": "Routes", "description": "Surface"},
    )
    collection_id = created.json()["id"]
    assert admin.get(f"/api/v1/knowledge/collections/{collection_id}").status_code == 200
    patched = admin.patch(
        f"/api/v1/knowledge/collections/{collection_id}",
        json={"description": "Updated"},
    )
    assert patched.status_code == 200
    source = admin.post(
        f"/api/v1/knowledge/collections/{collection_id}/sources",
        json={
            "name": "Site",
            "kind": "web",
            "config": {"items": [{"external_id": "p", "title": "Page", "text": "Desk opens"}]},
        },
    )
    assert source.status_code == 200
    source_id = source.json()["id"]
    assert admin.get(f"/api/v1/knowledge/collections/{collection_id}/sources").status_code == 200
    assert admin.get(f"/api/v1/knowledge/sources/{source_id}").status_code == 200
    assert (
        admin.patch(
            f"/api/v1/knowledge/sources/{source_id}",
            json={"name": "Site two"},
        ).status_code
        == 200
    )
    assert admin.post(f"/api/v1/knowledge/sources/{source_id}:test").status_code == 200
    assert (
        admin.post(
            f"/api/v1/knowledge/sources/{source_id}:sync",
            json={"mode": "incremental"},
        ).status_code
        == 202
    )
    assert admin.post(f"/api/v1/knowledge/sources/{source_id}:pause").status_code == 200
    assert admin.post(f"/api/v1/knowledge/sources/{source_id}:resume").status_code == 200
    upload = admin.post(
        "/api/v1/files:upload",
        files={"upload": ("note.md", b"# Note\n\nThe desk opens at 08:30.\n", "text/markdown")},
        data={"mime_type": "text/markdown"},
    )
    assert upload.status_code == 200
    added = admin.post(
        f"/api/v1/knowledge/collections/{collection_id}/documents",
        json={"fileIds": [upload.json()["id"]]},
    )
    assert added.status_code == 202
    document_id = added.json()["documents"][0]["id"]
    assert admin.get(f"/api/v1/knowledge/collections/{collection_id}/documents").status_code == 200
    assert admin.get(f"/api/v1/knowledge/documents/{document_id}").status_code == 200
    assert admin.get(f"/api/v1/knowledge/documents/{document_id}/chunks").status_code == 200
    assert admin.post(f"/api/v1/knowledge/documents/{document_id}:reingest").status_code == 202
    jobs = admin.get(f"/api/v1/knowledge/collections/{collection_id}/jobs")
    assert jobs.status_code == 200
    job_id = jobs.json()["items"][-1]["id"]
    assert admin.get(f"/api/v1/knowledge/jobs/{job_id}").status_code == 200
    assert admin.post(f"/api/v1/knowledge/jobs/{job_id}:cancel").status_code == 200
    reindex = admin.post(
        f"/api/v1/knowledge/collections/{collection_id}:reindex",
        json={
            "embeddingAlias": "fake-embed",
            "targetBackend": "pgvector",
            "textSearchConfig": "english",
        },
    )
    assert reindex.status_code == 202
    assert admin.delete(f"/api/v1/knowledge/documents/{document_id}").status_code == 202
    assert admin.delete(f"/api/v1/knowledge/sources/{source_id}").status_code == 202
    assert admin.delete(f"/api/v1/knowledge/collections/{collection_id}").status_code == 202
