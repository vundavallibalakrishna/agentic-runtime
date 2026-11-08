"""The agent drives real Chromium inside the browser container. Task: M40-T04b.

A canary: it needs a docker daemon and the ``ar-sandbox-browser`` image (built with
``--build-arg WITH_BROWSER=1``) and skips when either is missing (OQ-37).
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from typing import Any

import httpx
import pytest

from ar_common.sandbox_docker import image_present, start_sandbox, stop_sandbox

pytestmark = pytest.mark.integration

IMAGE = "ar-sandbox-browser:dev"
_PAGE = base64.b64encode(
    b"<html><head><title>AR Test</title></head><body>"
    b"<h1 id='h'>hello browser</h1>"
    b"<button onclick=\"document.getElementById('h').innerText='clicked'\">Go</button>"
    b"</body></html>"
).decode()


def _mcp(client: httpx.Client, endpoint: str, name: str, arguments: dict[str, Any]) -> dict:
    res = client.post(
        f"{endpoint}/mcp",
        headers={"Authorization": "Bearer canary"},
        json={"name": name, "arguments": arguments},
    )
    res.raise_for_status()
    return res.json()


def test_the_agent_drives_a_real_page() -> None:
    if not asyncio.run(image_present(IMAGE)):
        pytest.skip("docker daemon and the ar-sandbox-browser image are required")
    name = f"ar-sbx-browser-{uuid.uuid4().hex[:8]}"
    info = asyncio.run(start_sandbox(IMAGE, name, token="canary"))  # noqa: S106 - test credential
    endpoint = str(info["endpoint_url"])
    try:
        with httpx.Client(timeout=60.0) as client:
            nav = _mcp(client, endpoint, "navigate", {"url": f"data:text/html;base64,{_PAGE}"})
            assert nav["structured"]["title"] == "AR Test"
            refs = [e["ref"] for e in nav["structured"]["elements"]]
            assert refs, "no interactive elements were found"

            # Click the button and confirm the page text changed.
            clicked = _mcp(client, endpoint, "click", {"ref": refs[0]})
            assert "clicked" in clicked["structured"]["text"]

            # A real screenshot comes back as PNG bytes.
            shot = _mcp(client, endpoint, "screenshot", {})
            png = base64.b64decode(shot["structured"]["image_base64"])
            assert png[:4] == b"\x89PNG"
            assert shot["structured"]["bytes"] > 0
    finally:
        asyncio.run(stop_sandbox(str(info["container_id"])))
