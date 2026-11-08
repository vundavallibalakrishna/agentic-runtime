"""A registered launcher makes ensure_scope start a real container and run_tool use it.

End to end for M40-T01e: the whole wired path, not just the proxy. A canary that needs a
docker daemon and the ``ar-sandbox`` image and skips when either is missing (OQ-37).
"""

from __future__ import annotations

import asyncio

import pytest

from ar_common.sandbox_docker import DockerSandboxLauncher, image_present
from ar_domain.chat.service import demo_id
from ar_domain.sandboxes.runtime import ensure_scope, run_tool, terminate_row
from ar_testing.demo import demo_store

pytestmark = pytest.mark.integration

IMAGE = "ar-sandbox:dev"


def test_ensure_scope_starts_a_container_and_run_tool_uses_it() -> None:
    if not asyncio.run(image_present(IMAGE)):
        pytest.skip("docker daemon and the ar-sandbox image are required")
    store = demo_store()
    store.sandbox_launcher = DockerSandboxLauncher(IMAGE)
    conversation_id = demo_id("launch-e2e-conv")
    row = ensure_scope(
        store,
        tenant_id=demo_id("tenant"),
        template_slug="python-data",
        scope="conversation",
        scope_key=f"conv:{conversation_id}",
        conversation_id=conversation_id,
        agent_id=None,
        user_id=demo_id("admin"),
    )
    try:
        assert row["status"] == "ready"
        assert str(row["endpoint_url"]).startswith("http://127.0.0.1:")
        assert row["container_id"]

        # A tool call resolves the same scope and runs inside that container, not the host.
        args = {
            "command": 'python3 -c "print(6*7)"',
            "_tenant_id": demo_id("tenant"),
            "_user_id": demo_id("admin"),
            "_conversation_id": conversation_id,
        }
        ran = run_tool(store, "exec", args)
        assert ran["structured"]["exit_code"] == 0
        assert "42" in ran["structured"]["stdout"]
    finally:
        terminate_row(store, row, actor=demo_id("admin"))
    assert row["status"] == "terminated"
    assert row["container_id"] is None
