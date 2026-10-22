"""Files, sandboxes and browser. Spec: docs/03-specs/12-sandbox-manager.md."""

import threading
import uuid
from datetime import timedelta

import pytest

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.sandboxkit import (
    confine,
    download_headers,
    helper_verdict,
    host_denied,
    transition,
    truncate_output,
)
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.sandboxes.runtime import (
    chart_command,
    ensure_scope,
    read_workspace,
    resume_row,
    run_tool,
    suspend,
    workspace_root,
)
from ar_domain.sandboxes.service import SandboxBook
from ar_domain.tools.pipeline import ToolPipeline


def _actor(tenant: uuid.UUID | None = None) -> Actor:
    return Actor(tenant or demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)


def test_lifecycle_confinement_truncation_and_headers() -> None:
    assert transition("ready", "suspend") == "suspending"
    try:
        transition("terminated", "touch")
    except ValueError:
        pass
    else:
        raise AssertionError("illegal transition")
    root = workspace_root(uuid.uuid4())
    inside = confine(root, "/workspace/outputs/chart.png")
    assert inside.is_relative_to(root / "workspace")
    try:
        confine(root, "/etc/passwd")
    except ValueError:
        pass
    else:
        raise AssertionError("escape")
    link = root / "workspace" / "escape"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(root.parent)
    try:
        confine(root, "/workspace/escape/secret")
    except ValueError:
        pass
    else:
        raise AssertionError("symlink escape")
    text, err, truncated = truncate_output(b"x" * 20000, b"y" * 9000)
    assert truncated and len(text) < 20000 and len(err) < 9000
    headers = download_headers("page.html", "text/html", inline=True)
    assert headers["Content-Type"] == "application/octet-stream"
    assert headers["Content-Disposition"].startswith("attachment")
    assert "sandbox" in headers["Content-Security-Policy"]
    assert helper_verdict(200) == "OK"
    assert helper_verdict(403) == "ERR"
    assert host_denied("169.254.169.254", ("169.254.169.254/32",), lambda host: [host])


def test_template_limits_isolation_and_platform_lock() -> None:
    store = ChatService()
    book = SandboxBook(store)
    actor = _actor()
    created = book.create_template(actor, {"slug": "tiny", "name": "Tiny", "cpu_millis": 1000})
    assert created["slug"] == "tiny"
    try:
        book.create_template(actor, {"slug": "huge", "name": "Huge", "cpu_millis": 999999})
    except ValidationFailedError:
        pass
    else:
        raise AssertionError("plan limit")
    template_id = uuid.UUID(str(created["id"]))
    other = Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)
    try:
        book.patch_template(other, template_id, {"name": "stolen"})
    except NotFoundError:
        pass
    else:
        raise AssertionError("cross tenant")
    platform = next(row for row in store.sandbox_templates.values() if row["slug"] == "default")
    try:
        book.delete_template(actor, platform["id"])
    except ConflictError:
        pass
    else:
        raise AssertionError("platform delete")


def test_chart_package_gate_browser_and_resume() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    agent = next(row for row in store.agents.values() if row.get("slug") == "revenue-analyst")
    version_id = agent["published_version_id"]
    tool = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "sandbox.exec"
    )
    command = chart_command()
    result = ToolPipeline(store).execute(
        {
            "tenant_id": tenant,
            "user_id": user,
            "agent_id": agent["id"],
            "agent_version_id": version_id,
            "tool_version_id": tool["id"],
            "arguments": {"command": command, "timeout_s": 30},
            "run_id": None,
        }
    )
    assert result["status"] == "succeeded"
    assert "wrote revenue-by-month.png" in str(result["result_preview"])
    png = next(
        blob
        for file_id, blob in store.blobs.items()
        if str(store.files[file_id].get("name", "")).endswith(".png")
        and store.files[file_id].get("kind") == "artifact"
    )
    assert png.startswith(b"\x89PNG")
    denied = run_tool(
        store,
        "exec",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "_agent_version_id": version_id,
            "command": "pip install requests",
        },
    )
    assert denied["code"] == "egress_denied"
    science = store.versions[version_id]["definition"]
    science["sandbox"] = {"enabled": True, "template": "data-science", "scope": "agent"}
    allowed = run_tool(
        store,
        "exec",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "_agent_id": agent["id"],
            "_agent_version_id": version_id,
            "command": "pip install --help",
        },
    )
    assert allowed.get("code") != "egress_denied"
    science["sandbox"] = {"enabled": True, "template": "browser", "scope": "conversation"}
    page = run_tool(
        store,
        "navigate",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "_agent_id": agent["id"],
            "_agent_version_id": version_id,
            "_conversation_id": uuid.uuid4(),
            "url": "https://example.com",
        },
    )
    if not page.get("is_error"):
        assert "Example Domain" in str(page.get("text"))
        assert "[ref=e" in str(page.get("text"))
    submit = next(
        row
        for row in store.tool_versions.values()
        if row["qualified_name"] == "browser.submit_form"
    )
    held = ToolPipeline(store).execute(
        {
            "tenant_id": tenant,
            "user_id": user,
            "agent_id": agent["id"],
            "agent_version_id": version_id,
            "tool_version_id": submit["id"],
            "arguments": {"ref": "e1"},
        }
    )
    assert held["status"] == "awaiting_approval"
    sandbox = next(iter(store.sandboxes.values()))
    root = workspace_root(sandbox["id"])
    (root / "workspace" / "keep.txt").write_text("kept", encoding="utf-8")
    suspend(store, sandbox)
    (root / "workspace" / "keep.txt").unlink()
    resume_row(store, sandbox)
    assert read_workspace(sandbox, "/workspace/keep.txt") == b"kept"


def test_concurrent_ensure_and_cap() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    found: list[str] = []

    def once() -> None:
        row = ensure_scope(
            store,
            tenant_id=tenant,
            template_slug="python-data",
            scope="conversation",
            scope_key="conv:same",
            conversation_id=None,
            agent_id=None,
            user_id=demo_id("admin"),
        )
        found.append(str(row["id"]))

    threads = [threading.Thread(target=once) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(set(found)) == 1
    store.tenant_settings[tenant]["plan_limits"] = {"max_concurrent_sandboxes": 1}
    with pytest.raises(RuntimeError, match="limit"):
        ensure_scope(
            store,
            tenant_id=tenant,
            template_slug="python-data",
            scope="agent",
            scope_key="agent:other",
            conversation_id=None,
            agent_id=None,
            user_id=demo_id("admin"),
        )


def test_reap_suspends_idle() -> None:
    from ar_domain.sandboxes.runtime import reap

    store = ChatService()
    row = ensure_scope(
        store,
        tenant_id=demo_id("tenant"),
        template_slug="python-data",
        scope="conversation",
        scope_key="conv:idle",
        conversation_id=None,
        agent_id=None,
        user_id=demo_id("admin"),
    )
    template = store.sandbox_templates[row["template_id"]]
    template["idle_suspend_s"] = 1
    template["max_lifetime_s"] = 10**9
    row["last_active_at"] = utcnow() - timedelta(seconds=30)
    outcome = reap(store)
    assert outcome["suspended"] == 1
    assert row["status"] == "suspended"
