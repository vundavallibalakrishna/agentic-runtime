"""Sandbox HTTP surface, including cross-tenant 404 and HTML download headers."""

import uuid

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _client(tenant: uuid.UUID | None = None) -> TestClient:
    app = create_application()
    principal = Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=tenant or demo_id("tenant"),
        permissions=PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email="admin@dev.local",
        display_name="Dev Admin",
        roles=frozenset({"tenant_admin"}),
    )

    async def resolve(scope: object) -> Principal:
        del scope
        return principal

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    return TestClient(app)


def test_templates_chart_message_and_html_download() -> None:
    client = _client()
    templates = client.get("/api/v1/sandbox-templates")
    assert templates.status_code == 200
    slugs = {item["slug"] for item in templates.json()["items"]}
    assert {"default", "python-data", "browser", "data-science"} <= slugs
    huge = client.post(
        "/api/v1/sandbox-templates",
        json={"slug": "huge", "name": "Huge", "cpuMillis": 999999},
    )
    assert huge.status_code == 422
    agents = client.get("/api/v1/agents")
    analyst = next(row for row in agents.json()["items"] if row["slug"] == "revenue-analyst")
    created = client.post("/api/v1/conversations", json={"agentId": analyst["id"]})
    assert created.status_code == 200
    conversation = created.json()["id"]
    posted = client.post(
        f"/api/v1/conversations/{conversation}/messages",
        json={"text": "Analyse the attached CSV and chart revenue by month"},
    )
    assert posted.status_code == 202
    thread = client.get(f"/api/v1/conversations/{conversation}")
    assert "revenue-by-month.png" in thread.text
    files = client.get(f"/api/v1/files?conversationId={conversation}")
    assert files.status_code == 200
    png = next(item for item in files.json()["items"] if str(item["name"]).endswith(".png"))
    content = client.get(f"/api/v1/files/{png['id']}/content")
    assert content.status_code == 200
    assert content.content.startswith(b"\x89PNG")
    html_id = _html(client)
    download = client.get(f"/api/v1/files/{html_id}/content")
    assert download.headers["content-type"].startswith("application/octet-stream")
    assert download.headers["content-disposition"].startswith("attachment")
    made = client.post("/api/v1/sandbox-templates", json={"slug": "local", "name": "Local"})
    assert made.status_code == 200
    outsider = _client(uuid.uuid4())
    hidden = outsider.patch(
        f"/api/v1/sandbox-templates/{made.json()['id']}",
        json={"name": "Stolen"},
    )
    assert hidden.status_code == 404


def _html(client: TestClient) -> str:
    created = client.post(
        "/api/v1/files:upload",
        files={"upload": ("page.html", b"<html><script>nope</script></html>", "text/html")},
        data={"mime_type": "text/html"},
    )
    if created.status_code == 201:
        return str(created.json()["id"])
    store = client.app.state.chat
    from ar_common.ids import new_id

    file_id = new_id()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": demo_id("tenant"),
        "owner_user_id": demo_id("admin"),
        "name": "page.html",
        "mime_type": "text/html",
        "status": "ready",
        "created_at": store.files[next(iter(store.files))]["created_at"],
    }
    store.blobs[file_id] = b"<html><script>nope</script></html>"
    return str(file_id)
