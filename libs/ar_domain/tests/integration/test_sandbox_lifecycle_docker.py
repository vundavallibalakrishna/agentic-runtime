"""A computer's whole life against a real docker daemon: suspended, resumed, ended, cleaned up.

A canary that needs a docker daemon and the ``ar-sandbox`` image and skips when either
is missing (OQ-37). It names its own install, so the sweep it runs can only ever see the
containers this test started, and it removes every one of them even when it fails.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from ar_common.sandbox_docker import (
    DockerSandboxLauncher,
    image_present,
    list_sandboxes,
    sandbox_labels,
    start_sandbox,
    stop_sandbox,
)
from ar_common.settings import BaseServiceSettings, get_settings, set_settings
from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.sandboxes.lifecycle import sweep
from ar_domain.sandboxes.manager_launch import process_owner
from ar_domain.sandboxes.runtime import run_tool
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.integration

IMAGE = "ar-sandbox:dev"


@pytest.fixture
def installs(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, str, list[str]]]:
    """Two install ids of this test's own, and the removal of whatever carries them."""
    if not asyncio.run(image_present(IMAGE)):
        pytest.skip("docker daemon and the ar-sandbox image are required")
    mine, theirs = f"lc-test-{uuid.uuid4().hex[:10]}", f"lc-other-{uuid.uuid4().hex[:10]}"
    named: list[str] = []
    monkeypatch.setenv("AR_INSTALL_ID", mine)
    monkeypatch.setenv("AR_SANDBOX_ORPHAN_GRACE_S", "0")
    before = get_settings()
    set_settings(BaseServiceSettings())
    try:
        yield mine, theirs, named
    finally:
        set_settings(before)
        asyncio.run(_remove_all([mine, theirs], named))


async def _remove_all(install_ids: list[str], names: list[str]) -> None:
    for install in install_ids:
        for item in await list_sandboxes(install):
            await stop_sandbox(str(item["container_id"]))
    for name in names:
        await stop_sandbox(name)


async def _exists(name: str) -> bool:
    import aiodocker

    docker = aiodocker.Docker()
    try:
        found = await docker.containers.list(all=True, filters={"name": [f"^/{name}$"]})
    finally:
        await docker.close()
    return bool(found)


def _exec(store: Any, conversation: uuid.UUID, command: str) -> dict[str, Any]:
    who = {
        "_tenant_id": demo_id("tenant"),
        "_user_id": demo_id("admin"),
        "_conversation_id": conversation,
    }
    return run_tool(store, "exec", {"command": command, **who})


def _row(store: Any, conversation: uuid.UUID) -> dict[str, Any]:
    return next(
        row for row in store.sandboxes.values() if row.get("conversation_id") == conversation
    )


async def test_a_computer_lives_and_ends_on_a_real_daemon(
    installs: tuple[str, str, list[str]],
) -> None:
    mine, theirs, named = installs
    store = demo_store()
    store.sandbox_launcher = DockerSandboxLauncher(IMAGE, install_id=mine, owner=process_owner())
    tenant, user = demo_id("tenant"), demo_id("admin")

    # A tool call starts a labelled container and writes into its working folder.
    conversation = uuid.uuid4()
    wrote = _exec(
        store,
        conversation,
        "mkdir -p deep/empty && printf kept > deep/note.txt && chmod 755 deep/note.txt "
        "&& ln -s deep/note.txt link && printf lost > /home/sandbox/outside.txt",
    )
    assert wrote["structured"]["exit_code"] == 0, wrote
    row = _row(store, conversation)
    first = f"ar-sbx-{row['id'].hex[:12]}"
    listed = await list_sandboxes(mine)
    assert [item["name"] for item in listed] == [first]
    wanted = sandbox_labels(
        install_id=mine, owner=process_owner(), sandbox_id=str(row["id"]), tenant_id=str(tenant)
    )
    labels = listed[0]["labels"]
    assert isinstance(labels, dict)
    assert wanted.items() <= labels.items()

    # Idle: the sweep copies the folder to the object store and removes the container.
    template = store.sandbox_templates[row["template_id"]]
    template["idle_suspend_s"] = 60
    row["last_active_at"] = utcnow() - timedelta(seconds=120)
    assert await sweep(store) == {"suspended": 1, "terminated": 0, "removed": 0}
    assert row["status"] == "suspended"
    assert not await _exists(first)
    assert await list_sandboxes(mine) == []
    assert store.files[row["snapshot_file_id"]]["kind"] == "sandbox_snapshot"

    # The next tool call brings a new container up with the folder as it was.
    read = _exec(
        store,
        conversation,
        "cat link && test -x deep/note.txt && ls deep && ls /home/sandbox && ls -a",
    )
    assert read["structured"]["exit_code"] == 0, read
    out = read["structured"]["stdout"].split()
    assert out[:2] == ["keptempty", "note.txt"]
    # What was outside the working folder did not survive, and no copy pieces are left.
    assert "outside.txt" not in out
    assert ".ar-suspend" not in out
    assert row["status"] == "ready"
    assert await _exists(first)

    # Past its lifetime: ended, and the container removed.
    template["max_lifetime_s"] = 60
    row["started_at"] = utcnow() - timedelta(seconds=120)
    assert await sweep(store) == {"suspended": 0, "terminated": 1, "removed": 0}
    assert row["status"] == "terminated"
    assert not await _exists(first)
    template["max_lifetime_s"] = 86400

    # Deleting a conversation ends its computer.
    talk = uuid.UUID(str(store.create_conversation(tenant, user, None)["id"]))
    assert _exec(store, talk, "true")["structured"]["exit_code"] == 0
    second = f"ar-sbx-{_row(store, talk)['id'].hex[:12]}"
    assert await _exists(second)
    store.delete_conversation(tenant, user, talk)
    assert _row(store, talk)["status"] == "terminated"
    assert not await _exists(second)

    # Orphans: only a container with the product label and this install's id is removed.
    stem = f"lc-test-{uuid.uuid4().hex[:8]}"
    orphan, foreign, plain = f"{stem}-orphan", f"{stem}-foreign", f"{stem}-plain"
    named.extend([orphan, foreign, plain])
    lost = str(uuid.uuid4())
    await start_sandbox(
        IMAGE,
        orphan,
        token="canary",  # noqa: S106 - test credential
        labels=sandbox_labels(
            install_id=mine, owner=process_owner(), sandbox_id=lost, tenant_id=str(tenant)
        ),
    )
    await start_sandbox(
        IMAGE,
        foreign,
        token="canary",  # noqa: S106 - test credential
        labels=sandbox_labels(
            install_id=theirs, owner=process_owner(), sandbox_id=lost, tenant_id=str(tenant)
        ),
    )
    await start_sandbox(IMAGE, plain, token="canary")  # noqa: S106 - test credential
    assert await sweep(store) == {"suspended": 0, "terminated": 0, "removed": 1}
    assert not await _exists(orphan)
    assert await _exists(foreign)
    assert await _exists(plain)
