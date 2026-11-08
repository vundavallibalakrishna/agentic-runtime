"""The runtime routes the browser tools to real Chromium in the container. Task: M40-T04c.

End to end through ``run_tool``: a snapshot and a real screenshot reach the container, and a
denied navigation is stopped before it. A canary needing the ``ar-sandbox-browser`` image
(built with ``--build-arg WITH_BROWSER=1``); skips when docker or the image is missing.
"""

from __future__ import annotations

import asyncio
import uuid

import orjson
import pytest

from ar_common.sandbox_docker import DockerSandboxLauncher, image_present
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.sandboxes.browser_auth import BrowserConnectionBook
from ar_domain.sandboxes.runtime import ensure_scope, run_tool, terminate_row
from ar_testing.demo import demo_store

pytestmark = pytest.mark.integration

IMAGE = "ar-sandbox-browser:dev"


def test_browser_tools_run_in_the_container_through_run_tool() -> None:
    if not asyncio.run(image_present(IMAGE)):
        pytest.skip("docker daemon and the ar-sandbox-browser image are required")
    store = demo_store()
    store.sandbox_launcher = DockerSandboxLauncher(IMAGE)
    conversation_id = demo_id("browser-e2e-conv")
    row = ensure_scope(
        store,
        tenant_id=demo_id("tenant"),
        template_slug="browser",
        scope="conversation",
        scope_key=f"conv:{conversation_id}",
        conversation_id=conversation_id,
        agent_id=None,
        user_id=demo_id("admin"),
    )
    ctx = {
        "_tenant_id": demo_id("tenant"),
        "_user_id": demo_id("admin"),
        "_conversation_id": conversation_id,
    }
    try:
        assert row["endpoint_url"]

        # A snapshot reaches the container's real page (blank until navigation).
        snap = run_tool(store, "snapshot", {**ctx})
        assert snap["is_error"] is False
        assert "url" in snap["structured"]

        # A denied navigation is stopped by the egress gate, never reaching the container.
        denied = run_tool(store, "navigate", {**ctx, "url": "http://169.254.169.254/latest"})
        assert denied["is_error"] is True
        assert denied["code"] == "egress_denied"

        # A real screenshot comes back as a stored PNG artifact shown inline.
        shot = run_tool(store, "screenshot", {**ctx})
        assert shot["is_error"] is False
        file_id = uuid.UUID(str(shot["structured"]["file_id"]))
        assert store.files[file_id]["mime_type"] == "image/png"
        assert bytes(store.blobs[file_id])[:4] == b"\x89PNG"
        assert shot["structured"]["engine"] == "chromium"

        # The page saves as a real PDF artifact.
        pdf = run_tool(store, "save_pdf", {**ctx})
        assert pdf["is_error"] is False
        pdf_id = uuid.UUID(str(pdf["structured"]["file_id"]))
        assert store.files[pdf_id]["mime_type"] == "application/pdf"
        assert bytes(store.blobs[pdf_id])[:5] == b"%PDF-"

        # Tabs: open a second tab, list both, switch and close it.
        assert run_tool(store, "new_tab", {**ctx})["is_error"] is False
        tabs = run_tool(store, "tabs", {**ctx})
        assert len(tabs["structured"]["tabs"]) >= 2
        assert run_tool(store, "switch_tab", {**ctx, "index": 0})["is_error"] is False
        assert run_tool(store, "close_tab", {**ctx, "index": 1})["is_error"] is False

        # Stored sign-in: a connection's state restores into the container context, and the
        # model's result carries only the opaque handle — never the state (M40-T05c).
        BrowserConnectionBook(store).create(
            Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS),
            name="demo",
            origins=[],
            storage_state=orjson.dumps({"cookies": [], "origins": []}),
        )
        signin = run_tool(store, "use_connection", {**ctx, "connection": "demo"})
        assert signin["is_error"] is False
        assert signin["structured"]["status"] == "authenticated"
        assert run_tool(store, "snapshot", {**ctx})["is_error"] is False
    finally:
        terminate_row(store, row, actor=demo_id("admin"))
