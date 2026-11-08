"""Sandbox tools run inside a real container when the sandbox has an endpoint. Task: M40-T01d.

A canary: it needs a docker daemon and the ``ar-sandbox`` image and skips when either is
missing (OQ-37).
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from typing import Any

import pytest

from ar_domain.demo_ids import demo_id
from ar_domain.sandboxes.runtime import _exec_remote, _proxy
from ar_sandbox_manager.drivers.docker import start_sandbox, stop_sandbox
from ar_testing.demo import demo_store

pytestmark = pytest.mark.integration

IMAGE = "ar-sandbox:dev"
_PNG = base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
).decode()


async def _image_present() -> bool:
    import aiodocker

    docker: Any = aiodocker.Docker()
    try:
        await docker.images.inspect(IMAGE)
    except Exception:  # noqa: BLE001 - a missing image or daemon means skip
        return False
    else:
        return True
    finally:
        await docker.close()


def _sandbox(info: dict[str, object]) -> dict[str, object]:
    return {
        "id": uuid.uuid4(),
        "tenant_id": demo_id("tenant"),
        "conversation_id": uuid.uuid4(),
        "endpoint_url": info["endpoint_url"],
        "agent_token": info["token"],
    }


def test_tools_run_in_the_container_and_export_artifacts() -> None:
    if not asyncio.run(_image_present()):
        pytest.skip("docker daemon and the ar-sandbox image are required")
    name = f"ar-sbx-exec-{uuid.uuid4().hex[:8]}"
    info = asyncio.run(start_sandbox(IMAGE, name, token="canary"))  # noqa: S106 - test credential
    try:
        store = demo_store()
        sandbox = _sandbox(info)

        # exec runs in the container and the file it wrote is exported as an artifact.
        ran = _exec_remote(store, sandbox, {"command": "printf 'report' > note.txt"})
        assert ran["structured"]["exit_code"] == 0
        artifacts = ran["structured"]["artifacts"]
        assert artifacts, "the written file was not exported"
        file_id = uuid.UUID(str(artifacts[0]))
        assert store.files[file_id]["name"] == "note.txt"

        # a PNG written by a command surfaces as an inline chart.
        drew = _exec_remote(
            store,
            sandbox,
            {
                "command": f'python3 -c "import base64,pathlib; '
                f"pathlib.Path('outputs/chart.png').parent.mkdir(exist_ok=True); "
                f"pathlib.Path('outputs/chart.png').write_bytes(base64.b64decode('{_PNG}'))\"",
            },
        )
        assert drew["structured"]["exit_code"] == 0
        presentation = drew["structured"].get("presentation")
        assert isinstance(presentation, dict) and presentation["kind"] == "chart"

        # write and read proxy to the container.
        _proxy(sandbox, "write_file", {"path": "/workspace/a.txt", "content": "xyz"})
        read = _proxy(sandbox, "read_file", {"path": "/workspace/a.txt"})
        assert read["structured"]["content"] == "xyz"

        listed = _proxy(sandbox, "list_files", {"path": "/workspace", "recursive": True})
        assert "a.txt" in listed["text"]
    finally:
        asyncio.run(stop_sandbox(str(info["container_id"])))
