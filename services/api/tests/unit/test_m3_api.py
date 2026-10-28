"""M3 HTTP surface: registry, builder, bundles, packs and preview chat."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _client(
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    permissions: frozenset[str] | None = None,
    team_permissions: frozenset[tuple[uuid.UUID, str]] | None = None,
) -> TestClient:
    app = create_application()
    tenant = tenant_id or demo_id("tenant")
    user = user_id or demo_id("admin")
    principal = Principal(
        kind="user",
        id=str(user),
        tenant_id=tenant,
        permissions=permissions if permissions is not None else PERMISSION_KEYS,
        team_permissions=team_permissions or frozenset(),
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Dev Admin",
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    return TestClient(app)


def _create(client: TestClient, slug: str, **extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "template": "support",
    }
    body.update(extra)
    response = client.post("/api/v1/agents", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_registry_filters_publish_and_rollback() -> None:
    client = _client()
    listed = client.get("/api/v1/agents", params={"q": "help", "status": "published"})
    assert listed.status_code == 200
    assert any(item["slug"] == "helpdesk" for item in listed.json()["items"])
    created = _create(client, "desk-one", description="Answers short questions")
    agent_id = created["id"]
    etag = created["etag"]
    renamed = client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "Desk One", "description": "Updated"},
        headers={"If-Match": str(etag)},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Desk One"
    stale = client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "Nope"},
        headers={"If-Match": "stale"},
    )
    assert stale.status_code == 412
    checked = client.post(f"/api/v1/agents/{agent_id}:validate", json={})
    assert checked.status_code == 200
    assert checked.json()["valid"] is True
    published = client.post(f"/api/v1/agents/{agent_id}:publish", json={"changeNote": "v1"})
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    saved = client.put(
        f"/api/v1/agents/{agent_id}/versions/draft",
        json={"definition": {"instructions": "Reply in one sentence."}, "changeNote": "shorter"},
    )
    assert saved.status_code == 200
    again = client.post(f"/api/v1/agents/{agent_id}:publish", json={"changeNote": "v2"})
    assert again.status_code == 200
    history = client.get(f"/api/v1/agents/{agent_id}/versions")
    assert history.status_code == 200
    assert {item["version"] for item in history.json()["items"]} >= {1, 2}
    rolled = client.post(
        f"/api/v1/agents/{agent_id}:rollback",
        json={"version": 1, "changeNote": "back"},
    )
    assert rolled.status_code == 200
    assert rolled.json()["publishedVersion"] == 3
    version = client.get(f"/api/v1/agents/{agent_id}/versions/published")
    assert version.status_code == 200
    assert version.json()["state"] == "published"
    copied = client.post(
        f"/api/v1/agents/{agent_id}:duplicate",
        json={"slug": "desk-copy", "name": "Desk Copy"},
    )
    assert copied.status_code == 200
    assert copied.json()["status"] == "draft"
    favourite = client.put(
        "/api/v1/me/agent-favourites",
        json={"agentId": agent_id, "favourite": True},
    )
    assert favourite.status_code == 200
    assert favourite.json()["favourite"] is True
    used = client.get(f"/api/v1/agents/{agent_id}/where-used")
    assert used.status_code == 200
    assert used.json()["routines"] == []
    disabled = client.post(
        f"/api/v1/agents/{agent_id}:disable",
        json={"reason": "maintenance", "cancelActive": True},
    )
    assert disabled.status_code == 200
    assert disabled.json()["disabled"] is True
    enabled = client.post(f"/api/v1/agents/{agent_id}:enable")
    assert enabled.status_code == 200
    assert enabled.json()["disabled"] is False
    archived = client.post(f"/api/v1/agents/{agent_id}:archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    restored = client.post(f"/api/v1/agents/{agent_id}:unarchive")
    assert restored.status_code == 200
    assert restored.json()["status"] == "published"
    draft = _create(client, "desk-temp")
    removed = client.delete(f"/api/v1/agents/{draft['id']}")
    assert removed.status_code == 200
    assert removed.json()["deleted"] is True
    missing = client.get(f"/api/v1/agents/{draft['id']}")
    assert missing.status_code == 404


def test_builder_bundle_and_pack_routes() -> None:
    client = _client()
    started = client.post(
        "/api/v1/builder/sessions",
        json={"instruction": "create an agent that reviews vendor SOC 2 reports and flags gaps"},
    )
    assert started.status_code == 200
    session_id = started.json()["sessionId"]
    view = client.get(f"/api/v1/builder/sessions/{session_id}")
    assert view.status_code == 200
    spec = view.json()["proposal"]["resources"][0]["spec"]
    assert spec["tools"][0]["server"] == "files"
    assert view.json()["validation"]["errors"] == []
    revised = client.post(
        f"/api/v1/builder/sessions/{session_id}/messages",
        json={"text": "Ask for the report name first."},
    )
    assert revised.status_code == 200
    applied = client.post(
        f"/api/v1/builder/sessions/{session_id}:apply",
        json={"mode": "create"},
    )
    assert applied.status_code == 200
    agent_id = applied.json()["agentId"]
    detail = client.get(f"/api/v1/agents/{agent_id}")
    assert detail.json()["status"] == "draft"
    updated = client.post(
        f"/api/v1/builder/sessions/{session_id}:apply",
        json={"mode": "update", "agentId": agent_id},
    )
    assert updated.status_code == 200
    exported = client.get(
        "/api/v1/bundles:export",
        params={"ids": agent_id},
        headers={"accept": "application/json"},
    )
    assert exported.status_code == 200
    assert exported.json()["kind"] == "Bundle"
    yaml_export = client.get("/api/v1/bundles:export", params={"ids": agent_id})
    assert yaml_export.status_code == 200
    assert "kind:" in yaml_export.text
    preview = client.post(
        "/api/v1/bundles:import",
        json={"yamlText": yaml_export.text, "dryRun": True},
    )
    assert preview.status_code == 200
    assert preview.json()["results"][0]["action"] in {"unchanged", "new_version", "create"}
    manifest = {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {"id": "notes", "version": "1.0.0", "name": "Notes"},
        "spec": {"resources": []},
    }
    installed = client.post("/api/v1/content-packs:install", json={"manifest": manifest})
    assert installed.status_code == 200
    listed = client.get("/api/v1/content-packs")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["packId"] == "notes"
    fetched = client.get("/api/v1/content-packs/notes")
    assert fetched.status_code == 200
    upgraded = client.post(
        "/api/v1/content-packs/notes:upgrade",
        json={
            "manifest": {**manifest, "metadata": {**manifest["metadata"], "version": "1.1.0"}},
            "acceptConflicts": False,
        },
    )
    assert upgraded.status_code == 200
    dropped = client.post("/api/v1/content-packs/notes:uninstall", json={"dropSchema": True})
    assert dropped.status_code == 403
    assert "step-up" in dropped.json()["detail"]
    removed = client.post("/api/v1/content-packs/notes:uninstall", json={"dropSchema": False})
    assert removed.status_code == 200
    hidden = _client(uuid.uuid4(), uuid.uuid4()).get("/api/v1/content-packs/notes")
    assert hidden.status_code == 404


def test_preview_chat_and_guard_rails() -> None:
    client = _client()
    created = _create(client, "preview-desk")
    version_id = created["draft"]["id"]
    opened = client.post("/api/v1/conversations", json={"agentVersionId": version_id})
    assert opened.status_code == 200
    assert opened.json()["isPreview"] is True
    conversation_id = opened.json()["id"]
    hidden = client.get("/api/v1/conversations")
    assert all(item["id"] != conversation_id for item in hidden.json()["items"])
    shown = client.get("/api/v1/conversations", params={"includePreviews": "true"})
    assert any(item["id"] == conversation_id for item in shown.json()["items"])
    other = _client(uuid.uuid4(), uuid.uuid4())
    assert other.get(f"/api/v1/agents/{created['id']}").status_code == 404
    assert other.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
    invalid = client.post("/api/v1/agents", json={"slug": "X", "name": "Bad"})
    assert invalid.status_code == 422
    duplicate = client.post(
        "/api/v1/agents",
        json={"slug": "preview-desk", "name": "Again", "template": "blank"},
    )
    assert duplicate.status_code == 409
    helpdesk = next(
        item for item in client.get("/api/v1/agents").json()["items"] if item["slug"] == "helpdesk"
    )
    blocked = client.delete(f"/api/v1/agents/{helpdesk['id']}")
    assert blocked.status_code == 409
    limited = _client(
        permissions=frozenset(
            key for key in PERMISSION_KEYS if key not in {"agents:manage_all", "agents:publish"}
        )
    )
    high = limited.post(
        "/api/v1/agents",
        json={"slug": "careful", "name": "Careful", "template": "blank", "riskTier": "high"},
    )
    assert high.status_code == 200
    refused = limited.post(f"/api/v1/agents/{high.json()['id']}:publish", json={"changeNote": "no"})
    assert refused.status_code == 403
    client.app.state.chat.builder_strict = True
    client.app.state.chat.builder_scripts = ["not-json", "still-not"]
    failed = client.post(
        "/api/v1/agents:draft-from-description",
        json={"description": "Summarise a weekly status note"},
    )
    assert failed.status_code == 502
    assert failed.json()["code"] == "upstream_error"
