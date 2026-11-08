"""Browser tools route to the container and keep the egress gate. Task: M40-T04c.

No container here: the agent call is replaced from the test, so these cover the routing,
the navigation gate and the real-screenshot artifact without Chromium.
"""

from __future__ import annotations

import base64
import uuid
from typing import TYPE_CHECKING

from ar_domain.chat.service import demo_id
from ar_domain.sandboxes import runtime
from ar_domain.sandboxes.service import SandboxBook
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    import pytest

# A 1x1 PNG the fake agent "captures".
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _sandbox(store: object) -> dict[str, object]:
    SandboxBook(store).ensure_platform()
    return {
        "id": uuid.uuid4(),
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("admin"),
        "template_id": demo_id("sandbox-template-browser"),
        "endpoint_url": "http://127.0.0.1:65535",
        "agent_token": "t",
    }


def test_a_denied_host_is_blocked_before_the_container(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    calls: list[str] = []
    monkeypatch.setattr(runtime, "_agent_post", lambda *a, **k: calls.append("called") or {})
    result = runtime._browser(
        store, _sandbox(store), "navigate", {"url": "http://169.254.169.254/latest"}
    )
    assert result["is_error"] is True
    assert result["code"] == "egress_denied"
    assert calls == [], "a denied navigation must not reach the container"


def test_a_read_tool_is_proxied_to_the_container(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    seen: dict[str, object] = {}

    def fake(sandbox: dict, tool: str, arguments: dict, **kw: object) -> dict:
        seen["tool"] = tool
        return {"text": "ok", "structured": {"title": "Page"}, "is_error": False}

    monkeypatch.setattr(runtime, "_agent_post", fake)
    result = runtime._browser(store, _sandbox(store), "snapshot", {})
    assert seen["tool"] == "snapshot"
    assert result["structured"]["title"] == "Page"
    assert result["is_error"] is False


def test_the_real_screenshot_becomes_an_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    encoded = base64.b64encode(_PNG).decode("ascii")
    monkeypatch.setattr(
        runtime,
        "_agent_post",
        lambda *a, **k: {"structured": {"image_base64": encoded, "bytes": len(_PNG)}},
    )
    result = runtime._browser(store, _sandbox(store), "screenshot", {})
    assert result["is_error"] is False
    file_id = uuid.UUID(str(result["structured"]["file_id"]))
    assert store.files[file_id]["name"] == "browser.png"
    assert store.blobs[file_id] == _PNG
    assert result["structured"]["engine"] == "chromium"
    presentation = result["structured"]["presentation"]
    assert isinstance(presentation, dict) and presentation["kind"] == "chart"


def test_save_pdf_becomes_a_pdf_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    pdf = b"%PDF-1.4 fake"
    encoded = base64.b64encode(pdf).decode("ascii")
    monkeypatch.setattr(
        runtime,
        "_agent_post",
        lambda *a, **k: {
            "structured": {
                "file_base64": encoded,
                "filename": "page.pdf",
                "mime_type": "application/pdf",
            }
        },
    )
    result = runtime._browser(store, _sandbox(store), "save_pdf", {})
    assert result["is_error"] is False
    file_id = uuid.UUID(str(result["structured"]["file_id"]))
    assert store.files[file_id]["name"] == "page.pdf"
    assert store.files[file_id]["mime_type"] == "application/pdf"
    assert store.blobs[file_id] == pdf
    # A PDF is not an image, so no inline chart presentation.
    assert "presentation" not in result["structured"]


def test_upload_is_proxied_to_the_container(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    seen: dict[str, object] = {}

    def fake(sandbox: dict, tool: str, arguments: dict, **kw: object) -> dict:
        seen["tool"] = tool
        return {"text": "attached", "structured": {"name": "a.txt"}, "is_error": False}

    monkeypatch.setattr(runtime, "_agent_post", fake)
    result = runtime._browser(
        store, _sandbox(store), "upload", {"ref": "e1", "path": "/workspace/a.txt"}
    )
    assert seen["tool"] == "upload"
    assert result["is_error"] is False
