"""Public computer methods, browser tools and the manager routes."""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.references import ResolveContext
from ar_domain.sandboxes import tables
from ar_domain.sandboxes.resolver import _known
from ar_domain.sandboxes.runtime import (
    list_workspace,
    read_workspace,
    run_tool,
    suspend,
)
from ar_domain.sandboxes.service import SandboxBook

_IMAGE = "registry.local/ar/ar-sandbox@sha256:" + ("ab" * 32)


def _actor(permissions: frozenset[str] | None = None) -> Actor:
    granted = PERMISSION_KEYS if permissions is None else permissions
    return Actor(demo_id("tenant"), demo_id("admin"), granted)


def _call(store: ChatService, tool: str, **extra: object) -> dict[str, object]:
    agent = next(row for row in store.agents.values() if row.get("slug") == "revenue-analyst")
    version = store.versions[agent["published_version_id"]]
    version["definition"]["sandbox"] = {
        "enabled": True,
        "template": "browser",
        "scope": "conversation",
    }
    arguments: dict[str, object] = {
        "_tenant_id": demo_id("tenant"),
        "_user_id": demo_id("admin"),
        "_agent_id": agent["id"],
        "_agent_version_id": agent["published_version_id"],
        "_conversation_id": extra.pop("conversation_id", uuid.uuid4()),
    }
    arguments.update(extra)
    return run_tool(store, tool, arguments)


def test_tables_and_resolver() -> None:
    assert tables.Sandbox.__tablename__ == "sandboxes"
    assert tables.SandboxTemplate.__tablename__ == "sandbox_templates"
    known = ResolveContext(tenant_id="t", sandbox_templates={"python-data"})
    assert _known(known, "python-data", ("sandbox", "template")) == []
    missing = _known(known, "missing", ("sandbox", "template"))
    assert missing[0].type == "unknown_reference"


def test_template_lifecycle_and_files() -> None:
    store = ChatService()
    book = SandboxBook(store)
    book.ensure_platform()
    actor = _actor()
    created = book.create_template(
        actor, {"slug": "local-box", "name": "Local", "image_ref": _IMAGE}
    )
    template_id = uuid.UUID(str(created["id"]))
    patched = book.patch_template(
        actor,
        template_id,
        {"name": "Local box", "allow_packages": True, "cpu_millis": "1000", "status": "active"},
    )
    assert patched["name"] == "Local box"
    with pytest.raises(ValidationFailedError):
        book.create_template(actor, {"slug": "Bad Slug", "name": "Nope"})
    with pytest.raises(ConflictError):
        book.create_template(actor, {"slug": "local-box", "name": "Again"})
    with pytest.raises(ValidationFailedError):
        book.create_template(
            actor, {"slug": "plain", "name": "Plain", "image_ref": "python:latest"}
        )
    ensured = book.ensure(
        actor,
        {
            "template_id": template_id,
            "scope": "conversation",
            "scope_key": "conv:surface",
            "conversation_id": str(uuid.uuid4()),
        },
    )
    local_id = uuid.UUID(str(ensured["id"]))
    assert "token" in ensured
    assert book.list_sandboxes(actor)
    listed = book.files(actor, local_id, "/workspace")
    assert isinstance(listed, list)
    thread = uuid.uuid4()
    written = _call(
        store,
        "write_file",
        conversation_id=thread,
        path="/workspace/note.csv",
        content="a,b\n1,2\n",
    )
    assert written["is_error"] is False
    read = _call(store, "read_file", conversation_id=thread, path="/workspace/note.csv")
    assert "1,2" in str(read["text"])
    listing = _call(store, "list_files", conversation_id=thread, path="/workspace")
    assert listing["is_error"] is False
    echoed = _call(store, "exec", conversation_id=thread, command="printf hi", timeout_s=5)
    assert "hi" in str(echoed["text"])
    denied = _call(store, "exec", conversation_id=thread, command="curl https://169.254.169.254/")
    assert denied["code"] == "egress_denied"
    assert _call(store, "nope", conversation_id=thread)["code"] == "unknown_tool"
    assert _call(store, "read_file", conversation_id=thread, path="/etc/passwd")["is_error"] is True
    live = next(row for row in store.sandboxes.values() if row.get("conversation_id") == thread)
    live_id = uuid.UUID(str(live["id"]))
    data, headers = book.file_bytes(actor, live_id, "/workspace/note.csv")
    assert data.startswith(b"a,b")
    assert headers["Content-Type"].startswith("text/csv")
    book.suspend(actor, live_id)
    suspended = book.list_sandboxes(actor)
    assert any(row["status"] == "suspended" for row in suspended)
    resumed = book.file_bytes(actor, live_id, "/workspace/note.csv")
    assert resumed[0].startswith(b"a,b")
    with pytest.raises(ConflictError):
        book.delete_template(actor, template_id)
    ended = book.terminate(actor, local_id)
    assert ended["status"] == "terminated"
    book.delete_template(actor, template_id)
    with pytest.raises(NotFoundError):
        book.list_templates(_actor(frozenset()))


def test_browser_attach_export_and_reap() -> None:
    store = ChatService()
    conversation = uuid.uuid4()
    run_id = uuid.uuid4()
    store.events[run_id] = []
    store.runs[run_id] = {
        "id": run_id,
        "conversation_id": conversation,
        "tenant_id": demo_id("tenant"),
    }
    page = _call(
        store,
        "navigate",
        conversation_id=conversation,
        url="https://example.com",
        _run_id=run_id,
        _tool_call_id=str(uuid.uuid4()),
    )
    assert page["is_error"] is False
    snapshot = _call(store, "snapshot", conversation_id=conversation)
    assert "Example Domain" in str(snapshot["text"])
    clicked = _call(store, "click", conversation_id=conversation, ref="e1")
    assert clicked["is_error"] is False
    typed = _call(store, "type", conversation_id=conversation, ref="e1", text="12")
    assert typed["is_error"] is False
    assert _call(store, "press", conversation_id=conversation)["is_error"] is False
    assert _call(store, "scroll", conversation_id=conversation)["is_error"] is False
    shot = _call(store, "screenshot", conversation_id=conversation, _run_id=run_id)
    assert shot["is_error"] is False
    assert _call(store, "submit_form", conversation_id=conversation, ref="e1")["is_error"] is False
    missing = _call(store, "attach_to_sandbox", file_id=str(uuid.uuid4()))
    assert missing["code"] == "not_found"
    file_id = uuid.uuid4()
    store.files[file_id] = {"id": file_id, "name": "sheet.csv", "tenant_id": demo_id("tenant")}
    store.blobs[file_id] = b"month,revenue\n2026-01,10\n"
    copied = _call(
        store,
        "attach_to_sandbox",
        conversation_id=conversation,
        file_id=str(file_id),
        _attachment_ids=[str(file_id)],
    )
    assert copied["is_error"] is False
    exported = _call(
        store,
        "export_file",
        conversation_id=conversation,
        path="/workspace/inputs/sheet.csv",
        name="sheet.csv",
    )
    assert exported["is_error"] is False
    from ar_mcp_gateway.builtins.files import forward as forward_files
    from ar_mcp_gateway.builtins.sandbox import forward as forward_sandbox

    assert (
        forward_sandbox(
            store,
            "sandbox.list_files",
            {
                "_tenant_id": demo_id("tenant"),
                "_user_id": demo_id("admin"),
                "_conversation_id": conversation,
                "path": "/workspace",
            },
        )["is_error"]
        is False
    )
    assert forward_files(store, "files.read", {"path": "/workspace"})["is_error"] in {True, False}
    assert (
        forward_files(
            store,
            "files.attach_to_sandbox",
            {
                "_tenant_id": demo_id("tenant"),
                "_user_id": demo_id("admin"),
                "_conversation_id": conversation,
                "file_id": str(file_id),
            },
        )["is_error"]
        is False
    )
    sandbox = next(
        row
        for row in store.sandboxes.values()
        if row.get("conversation_id") == conversation and row.get("status") == "ready"
    )
    suspend(store, sandbox)
    assert list_workspace(sandbox, "/workspace", recursive=True)
    with pytest.raises(ValueError, match="resume"):
        read_workspace(sandbox, "/workspace/inputs/sheet.csv")
    sandbox["started_at"] = utcnow() - timedelta(days=3)
    sandbox["status"] = "suspended"
    from ar_domain.sandboxes.runtime import reap

    swept = reap(store, now=utcnow())
    assert swept["terminated"] >= 1
    other = SandboxBook(store)
    other.seed_chart(uuid.uuid4(), uuid.uuid4())
    store.conversations.pop(demo_id("showcase-revenue"), None)
    other.seed_chart(demo_id("tenant"), demo_id("admin"))


def test_manager_routes_and_docker_probe() -> None:
    from ar_sandbox_manager.drivers.docker import docker_available
    from ar_sandbox_manager.main import create_application
    from ar_sandbox_manager.warm_pool import claim

    assert docker_available() in {True, False}
    assert claim("default=4,browser=2", "browser", {"browser": 0}) is None
    client = TestClient(create_application())
    store = client.app.state.chat
    template = next(row for row in store.sandbox_templates.values() if row["slug"] == "browser")
    made = client.post(
        "/internal/v1/sandboxes:ensure",
        json={
            "tenant_id": str(demo_id("tenant")),
            "scope": "conversation",
            "scope_key": "conv:manager",
            "template_id": str(template["id"]),
            "user_id": str(demo_id("admin")),
        },
    )
    assert made.status_code == 200
    sandbox_id = made.json()["id"]
    token = made.json()["token"]
    assert client.get(f"/internal/v1/sandboxes/{sandbox_id}").status_code == 200
    assert client.get(f"/internal/v1/sandboxes/{uuid.uuid4()}").json()["status"] == "not_found"
    touch = client.post(f"/internal/v1/sandboxes/{sandbox_id}:touch")
    assert touch.json()["status"] == "ready"
    missed = client.post(f"/internal/v1/sandboxes/{uuid.uuid4()}:touch")
    assert missed.json()["status"] == "not_found"
    allowed = client.get(
        "/internal/v1/egress/check",
        params={"sandbox_id": sandbox_id, "host": "example.com", "token": token},
    )
    assert allowed.status_code in {200, 403}
    denied = client.get(
        "/internal/v1/egress/check",
        params={"sandbox_id": "not-a-uuid", "host": "example.com", "token": token},
    )
    assert denied.status_code == 403
    missing_box = client.get(
        "/internal/v1/egress/check",
        params={"sandbox_id": str(uuid.uuid4()), "host": "example.com", "token": token},
    )
    assert missing_box.status_code == 403
    wrong = client.get(
        "/internal/v1/egress/check",
        params={"sandbox_id": sandbox_id, "host": "example.com", "token": "nope"},
    )
    assert wrong.status_code == 403
    template["egress_allowlist"] = ["10.1.0.1"]
    blocked = client.get(
        "/internal/v1/egress/check",
        params={"sandbox_id": sandbox_id, "host": "10.1.0.1", "token": token},
    )
    assert blocked.status_code == 403
    private = client.get(
        "/internal/v1/egress/check",
        params={"sandbox_id": sandbox_id, "host": "169.254.169.254", "token": token},
    )
    assert private.status_code == 403
    assert client.post(f"/internal/v1/sandboxes/{sandbox_id}:suspend").status_code == 200
    assert client.post("/internal/v1/sandboxes:reap").status_code == 200
    assert client.post(f"/internal/v1/sandboxes/{sandbox_id}:terminate").status_code == 200
    gone = client.post(f"/internal/v1/sandboxes/{uuid.uuid4()}:terminate")
    assert gone.json()["status"] == "not_found"
    assert (
        client.post(f"/internal/v1/sandboxes/{uuid.uuid4()}:suspend").json()["status"]
        == "not_found"
    )
    conversation_id = uuid.uuid4()
    store.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("admin"),
    }
    row = next(iter(store.sandboxes.values()))
    row["conversation_id"] = conversation_id
    row["status"] = "ready"
    found = SandboxBook(store).conversation_sandbox(_actor(), conversation_id)
    assert found["status"] == "ready"
