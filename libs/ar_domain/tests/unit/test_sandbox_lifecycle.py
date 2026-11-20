"""A computer is suspended, resumed, ended and cleaned up without anyone asking. Proof: unit.

The agent in these tests is the product's own sandbox agent, served in process over a
temporary folder. Docker is stood in for at the launcher: it records the containers it
was asked to start, with their labels, and loses the working folder when one stops, as
a real container does.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from ar_common import sandbox_docker
from ar_common.sandbox_docker import (
    LABEL_INSTALL,
    LABEL_OWNER,
    LABEL_PRODUCT,
    LABEL_SANDBOX,
    LABEL_TENANT,
    DockerSandboxLauncher,
    sandbox_labels,
)
from ar_common.settings import BaseServiceSettings, get_settings, install_id, set_settings
from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.sandboxes import lifecycle, runtime, snapshot
from ar_domain.sandboxes.lifecycle import (
    SandboxBusyError,
    SandboxKeeper,
    keeper_for,
    orphans,
    reconcile,
    scope_lock,
    stop_started,
    sweep,
)
from ar_domain.sandboxes.manager_launch import SandboxManagerLauncher, owner_gone, process_owner
from ar_domain.sandboxes.runtime import ensure_scope, reap, reap_one, run_tool, suspend
from ar_domain.sandboxes.service import SandboxBook
from ar_testing.demo import demo_store
from ar_testing.objects import RefusingObjectStore

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_ENDPOINT = "http://computer.test"
_INSTALL = "install-under-test"


class _Docker:
    """Stands in for the docker daemon behind a launcher.

    It keeps what a daemon would: the containers that run, each with the labels it was
    started with. Stopping one empties the working folder, because that folder lives in
    the container.
    """

    def __init__(self, root: Path, *, install: str = _INSTALL) -> None:
        self.root = root
        self.install_id = install
        self.owner = process_owner()
        self.running: dict[str, dict[str, object]] = {}
        self.started: list[str] = []
        self.stopped: list[str] = []
        self.legacy: list[str] = []

    def start(
        self, name: str, token: str, sandbox_id: str = "", tenant_id: str = ""
    ) -> dict[str, object]:
        self.started.append(name)
        self.running[name] = {
            "container_id": name,
            "name": name,
            "labels": sandbox_labels(
                install_id=self.install_id,
                owner=self.owner,
                sandbox_id=sandbox_id,
                tenant_id=tenant_id,
            ),
            "created": time.time(),
        }
        return {"container_id": name, "endpoint_url": _ENDPOINT, "token": token}

    def stop(self, container_id: str) -> None:
        self.stopped.append(container_id)
        if self.running.pop(container_id, None) is not None:
            shutil.rmtree(self.root / "workspace", ignore_errors=True)

    def containers(self) -> list[dict[str, object]]:
        # The daemon filters on the product label and this install's id.
        return [
            dict(item)
            for item in self.running.values()
            if _labels(item).get(LABEL_PRODUCT) == "true"
            and _labels(item).get(LABEL_INSTALL) == self.install_id
        ]

    def unlabelled(self) -> list[str]:
        return list(self.legacy)


def _labels(item: dict[str, object]) -> dict[str, str]:
    raw = item["labels"]
    assert isinstance(raw, dict)
    return raw


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[BaseServiceSettings]:
    """Settings of an install with a name, no grace period and a short wait for a busy scope."""
    monkeypatch.setenv("AR_INSTALL_ID", _INSTALL)
    monkeypatch.setenv("AR_SANDBOX_ORPHAN_GRACE_S", "0")
    monkeypatch.setenv("AR_SANDBOX_ENSURE_TIMEOUT_S", "1")
    before = get_settings()
    current = BaseServiceSettings()
    set_settings(current)
    yield current
    set_settings(before)


@pytest.fixture
def docker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, settings: BaseServiceSettings
) -> _Docker:
    """Serve the sandbox agent in process, and keep host folders under the test's own folder."""
    del settings
    from ar_sandbox_agent.main import create_application

    box = tmp_path / "box"
    box.mkdir()
    monkeypatch.setenv("AR_SANDBOX_ROOT", str(box))
    monkeypatch.delenv("AR_SANDBOX_TOKEN", raising=False)
    monkeypatch.setattr(runtime, "_ROOT", tmp_path / "host")
    agent = create_application()
    monkeypatch.setattr(
        runtime.httpx, "Client", lambda **_kw: TestClient(agent, base_url=_ENDPOINT)
    )
    return _Docker(box)


def _store(docker: _Docker) -> Any:
    store = demo_store()
    store.sandbox_launcher = docker
    return store


def _who(conversation: uuid.UUID) -> dict[str, object]:
    return {
        "_tenant_id": demo_id("tenant"),
        "_user_id": demo_id("admin"),
        "_conversation_id": conversation,
    }


def _exec(store: Any, conversation: uuid.UUID, command: str) -> dict[str, Any]:
    return run_tool(store, "exec", {"command": command, **_who(conversation)})


def _row(store: Any, conversation: uuid.UUID) -> dict[str, Any]:
    return next(
        row
        for row in store.sandboxes.values()
        if row.get("conversation_id") == conversation
        and row.get("status") not in {"terminated", "failed"}
    )


def _idle(store: Any, row: dict[str, Any], *, idle_s: int = 60, life_s: int = 10**9) -> None:
    template = store.sandbox_templates[row["template_id"]]
    template["idle_suspend_s"] = idle_s
    template["max_lifetime_s"] = life_s
    row["last_active_at"] = utcnow() - timedelta(seconds=idle_s + 30)


def _actions(store: Any) -> list[str]:
    return [str(item["action"]) for item in store.audit_log]


def test_an_idle_computer_is_suspended_and_its_container_removed(docker: _Docker) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    assert _exec(store, conversation, "printf kept > note.txt")["structured"]["exit_code"] == 0
    row = _row(store, conversation)
    name = str(row["container_id"])
    _idle(store, row)
    assert reap(store) == {"suspended": 1, "terminated": 0}
    assert row["status"] == "suspended"
    assert row["endpoint_url"] is None
    assert docker.stopped == [name]
    assert not docker.running
    # The working folder left the host with the container. Its bytes are in the object
    # store, under a file row any process can read.
    saved = store.files[row["snapshot_file_id"]]
    assert saved["kind"] == "sandbox_snapshot"
    assert store.objects.get(saved["object_key"]) is not None
    assert "sandbox.suspended" in _actions(store)
    # A second sweep finds nothing to do.
    assert reap(store) == {"suspended": 0, "terminated": 0}


def test_the_next_tool_call_resumes_the_computer_with_its_folder(docker: _Docker) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    made = "mkdir -p deep/empty && printf kept > deep/note.txt && chmod 755 deep/note.txt"
    assert _exec(store, conversation, made)["structured"]["exit_code"] == 0
    assert _exec(store, conversation, "ln -s deep/note.txt link")["structured"]["exit_code"] == 0
    row = _row(store, conversation)
    _idle(store, row)
    reap(store)
    assert not (docker.root / "workspace" / "deep").exists()
    row["last_active_at"] = utcnow()
    read = _exec(store, conversation, "cat link && test -x deep/note.txt && ls deep")
    assert read["structured"]["exit_code"] == 0, read
    # The file, its permissions, the link and the empty folder all came back.
    assert read["structured"]["stdout"].split() == ["keptempty", "note.txt"]
    assert row["status"] == "ready"
    assert len(docker.started) == 2
    assert len(docker.running) == 1
    assert _actions(store).count("sandbox.resumed") == 1
    # The pieces the copy used are not left in the folder.
    assert not (docker.root / "workspace" / ".ar-suspend").exists()


def test_a_suspended_computer_does_not_count_toward_the_cap(
    docker: _Docker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AR_SANDBOX_MAX_PER_TENANT", "1")
    store = _store(docker)
    first, second = uuid.uuid4(), uuid.uuid4()
    assert not _exec(store, first, "true")["is_error"]
    refused = _exec(store, second, "true")
    assert refused["code"] == "quota_exceeded"
    suspend(store, _row(store, first))
    assert not _exec(store, second, "true")["is_error"]
    # Coming back counts again: with the cap taken the computer stays suspended.
    again = _exec(store, first, "true")
    assert again["code"] == "quota_exceeded"
    assert _row(store, first)["status"] == "suspended"


def test_a_folder_that_cannot_be_copied_leaves_the_computer_running(
    docker: _Docker, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    _exec(store, conversation, "printf kept > note.txt")
    row = _row(store, conversation)
    _idle(store, row)

    def too_big(_sandbox: object, *, max_bytes: int) -> bytes:
        raise snapshot.SnapshotError(f"larger than {max_bytes}")

    monkeypatch.setattr(snapshot, "take", too_big)
    before = row["last_active_at"]
    assert reap(store) == {"suspended": 0, "terminated": 0}
    assert row["status"] == "ready"
    assert not docker.stopped
    # It is tried again after another idle period, not on every sweep.
    assert row["last_active_at"] > before
    assert "sandbox.suspended" not in _actions(store)
    with pytest.raises(Exception, match="larger than"):
        SandboxBook(store).suspend(_admin(), row["id"])


def test_a_snapshot_the_object_store_refuses_leaves_the_computer_running(
    docker: _Docker,
) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    _exec(store, conversation, "true")
    row = _row(store, conversation)
    _idle(store, row)
    store.objects = RefusingObjectStore()
    assert reap(store) == {"suspended": 0, "terminated": 0}
    assert row["status"] == "ready"
    assert not docker.stopped
    assert row.get("snapshot_file_id") is None


def test_a_snapshot_over_the_limit_is_refused(docker: _Docker) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    _exec(store, conversation, "head -c 300000 /dev/urandom > big.bin")
    row = _row(store, conversation)
    with pytest.raises(snapshot.SnapshotError, match="larger"):
        snapshot.take(row, max_bytes=100_000)
    assert not (docker.root / "workspace" / ".ar-suspend").exists()
    assert len(snapshot.take(row, max_bytes=1_000_000)) > 290_000


def test_a_folder_that_does_not_go_back_leaves_the_computer_suspended(
    docker: _Docker, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    _exec(store, conversation, "printf kept > note.txt")
    row = _row(store, conversation)
    suspend(store, row)

    def broken(_sandbox: object, _blob: bytes) -> None:
        raise snapshot.SnapshotError("the snapshot did not unpack")

    monkeypatch.setattr(snapshot, "put", broken)
    failed = _exec(store, conversation, "cat note.txt")
    assert failed["code"] == "sandbox_unavailable"
    assert "did not unpack" in failed["text"]
    # Nothing runs on an empty folder: the new container is gone and the snapshot kept.
    assert row["status"] == "suspended"
    assert not docker.running
    assert store.files[row["snapshot_file_id"]]["status"] == "ready"
    monkeypatch.undo()


def test_a_computer_past_its_lifetime_is_ended_with_everything_it_had(docker: _Docker) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    _exec(store, conversation, "printf kept > note.txt")
    row = _row(store, conversation)
    folder = runtime.workspace_root(row["id"])
    assert (folder / runtime.FOLDER_MARK).read_text().split() == [_INSTALL, process_owner()]
    suspend(store, row)
    snapshot_id = row["snapshot_file_id"]
    _idle(store, row, life_s=60)
    row["started_at"] = utcnow() - timedelta(seconds=120)
    assert reap(store) == {"suspended": 0, "terminated": 1}
    assert row["status"] == "terminated"
    assert store.files[snapshot_id]["status"] == "deleted"
    assert not folder.exists()
    assert "sandbox.terminated" in _actions(store)
    # A running computer past its lifetime is ended, not suspended first.
    other = uuid.uuid4()
    _exec(store, other, "true")
    late = _row(store, other)
    _idle(store, late, life_s=60)
    late["started_at"] = utcnow() - timedelta(seconds=120)
    assert reap_one(store, late) == "terminate"
    assert not docker.running


def test_deleting_a_conversation_ends_its_computer_and_no_other(docker: _Docker) -> None:
    store = _store(docker)
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = uuid.UUID(str(store.create_conversation(tenant, user, None)["id"]))
    _exec(store, conversation, "true")
    own = _row(store, conversation)
    shared = ensure_scope(
        store,
        tenant_id=tenant,
        template_slug="python-data",
        scope="agent",
        scope_key="agent:shared",
        conversation_id=conversation,
        agent_id=None,
        user_id=user,
    )
    assert len(docker.running) == 2
    store.delete_conversation(tenant, user, conversation)
    assert own["status"] == "terminated"
    assert str(own["id"]) in {item["target_id"] for item in store.audit_log}
    assert _actions(store).count("sandbox.terminated") == 1
    # A computer an agent shares across conversations is not this conversation's to end.
    assert shared["status"] == "ready"
    assert list(docker.running) == [str(shared["container_id"])]


def test_only_this_installs_labelled_containers_are_ever_orphans() -> None:
    now = time.time()
    me = process_owner()
    known = str(uuid.uuid4())

    def container(name: str, **labels: str) -> dict[str, object]:
        return {"container_id": name, "name": name, "labels": labels, "created": now - 600}

    def mine(name: str, sandbox: str, owner: str = me) -> dict[str, object]:
        labels = sandbox_labels(install_id=_INSTALL, owner=owner, sandbox_id=sandbox, tenant_id="t")
        return container(name, **labels)

    other_install = container(
        "other",
        **sandbox_labels(install_id="another", owner=me, sandbox_id="x", tenant_id="t"),
    )
    young = mine("young", "no-row")
    young["created"] = now - 5
    listed = [
        mine("no-row", "no-row"),
        mine("ended", "ended"),
        mine("suspended", "suspended"),
        mine("ready", known),
        young,
        other_install,
        container("ar-sbx-legacy"),
        container("half", **{LABEL_PRODUCT: "true"}),
    ]
    states = {known: "ready", "ended": "terminated", "suspended": "suspended"}
    found = orphans(listed, states, install=_INSTALL, me=me, shared_rows=True, now=now, grace_s=120)
    assert [item["name"] for item in found] == ["no-row", "ended", "suspended"]
    # With no install id nothing is an orphan, whatever is listed.
    assert not orphans(listed, states, install="", me=me, shared_rows=True, now=now, grace_s=0)


def test_another_running_process_of_the_install_keeps_its_containers() -> None:
    now = time.time()
    me = process_owner()
    host = me.rpartition(":")[0]
    alive = f"{host}:{os.getppid()}"
    dead = f"{host}:{_dead_pid()}"
    assert owner_gone(dead)
    assert not owner_gone(alive)
    assert not owner_gone("elsewhere:1")
    assert not owner_gone("unreadable")

    def mine(name: str, owner: str) -> dict[str, object]:
        labels = sandbox_labels(install_id=_INSTALL, owner=owner, sandbox_id=name, tenant_id="t")
        return {"container_id": name, "name": name, "labels": labels, "created": now - 600}

    listed = [mine("own", me), mine("live", alive), mine("left", dead), mine("far", "else:1")]
    # Rows kept in this process only: a container with no row here may be another
    # process's, so it goes only when this process started it or its starter is gone.
    local = orphans(listed, {}, install=_INSTALL, me=me, shared_rows=False, now=now, grace_s=0)
    assert [item["name"] for item in local] == ["own", "left"]
    # Rows in the database every process reads: no row means nobody owns it.
    shared = orphans(listed, {}, install=_INSTALL, me=me, shared_rows=True, now=now, grace_s=0)
    assert len(shared) == 4


def _dead_pid() -> int:
    import subprocess
    import sys

    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()
    return done.pid


async def test_the_sweep_removes_orphans_and_their_folders_and_only_reports_old_ones(
    docker: _Docker, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    _exec(store, conversation, "true")
    row = _row(store, conversation)
    kept = str(row["container_id"])
    host = runtime.host_root()
    lost = uuid.uuid4()
    # A container and a folder whose computer has no row, as a process that lost its
    # rows leaves them; another install's; and one from before the labels.
    docker.start("ar-sbx-lost", "t", sandbox_id=str(lost), tenant_id="t")
    (host / str(lost)).mkdir(parents=True)
    (host / str(lost) / runtime.FOLDER_MARK).write_text(f"{_INSTALL}\n{process_owner()}\n")
    foreign, unmarked = uuid.uuid4(), uuid.uuid4()
    (host / str(foreign)).mkdir()
    (host / str(foreign) / runtime.FOLDER_MARK).write_text("another-install\nx:1\n")
    (host / str(unmarked)).mkdir()
    other = sandbox_labels(install_id="another", owner="x:1", sandbox_id="s", tenant_id="t")
    docker.running["theirs"] = {
        "container_id": "theirs",
        "name": "theirs",
        "labels": other,
        "created": 0.0,
    }
    docker.running["ar-sbx-old"] = {
        "container_id": "ar-sbx-old",
        "name": "ar-sbx-old",
        "labels": {},
        "created": 0.0,
    }
    docker.legacy = ["ar-sbx-old"]
    lifecycle._reported.clear()
    assert await sweep(store) == {"suspended": 0, "terminated": 0, "removed": 1}
    assert sorted(docker.running) == sorted([kept, "theirs", "ar-sbx-old"])
    assert docker.stopped == ["ar-sbx-lost"]
    assert not (host / str(lost)).exists()
    assert (host / str(foreign)).exists()
    assert (host / str(unmarked)).exists()
    assert runtime.workspace_root(row["id"]).exists()
    logged = capsys.readouterr().out
    assert "sandbox_unlabelled_containers" in logged
    assert "ar-sbx-old" in logged
    # The report is made once, not on every sweep.
    assert await reconcile(store) == 0
    assert "sandbox_unlabelled_containers" not in capsys.readouterr().out


async def test_a_container_younger_than_the_grace_period_is_left(
    docker: _Docker, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(docker)
    docker.start("ar-sbx-new", "t", sandbox_id=str(uuid.uuid4()), tenant_id="t")
    monkeypatch.setenv("AR_SANDBOX_ORPHAN_GRACE_S", "120")
    set_settings(BaseServiceSettings())
    assert await reconcile(store) == 0
    assert "ar-sbx-new" in docker.running


async def test_the_keeper_sweeps_on_a_timer_and_ends_its_computers_on_shutdown(
    docker: _Docker,
) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    _exec(store, conversation, "true")
    row = _row(store, conversation)
    _idle(store, row)
    stray = uuid.uuid4()
    keeper = SandboxKeeper(store, interval_s=0.01)
    keeper.start()
    keeper.start()
    for _ in range(200):
        if row["status"] == "suspended":
            break
        await asyncio.sleep(0.02)
    assert row["status"] == "suspended"
    # Back in use, and one container whose row this process lost.
    assert not _exec(store, conversation, "true")["is_error"]
    docker.start("ar-sbx-stray", "t", sandbox_id=str(stray), tenant_id="t")
    docker.running["ar-sbx-stray"]["created"] = time.time() + 3600
    await keeper.stop()
    assert row["status"] == "terminated"
    assert not docker.running
    assert _actions(store).count("sandbox.terminated") == 1
    await keeper.stop()


def test_a_process_with_nothing_to_keep_has_no_keeper(docker: _Docker) -> None:
    store = _store(docker)
    assert isinstance(keeper_for(store), SandboxKeeper)
    store.sandbox_launcher = SandboxManagerLauncher("http://manager.test")
    assert keeper_for(store) is None
    assert stop_started(store) == 0


async def test_a_process_without_containers_asks_the_manager_to_sweep(
    monkeypatch: pytest.MonkeyPatch, settings: BaseServiceSettings
) -> None:
    del settings
    asked: list[str] = []

    class _Answer:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"suspended": 2, "terminated": 1, "removed": 3}

        def close(self) -> None:
            return None

    def post(url: str, **_kwargs: object) -> _Answer:
        asked.append(url)
        return _Answer()

    monkeypatch.setattr("ar_domain.sandboxes.manager_launch.internal_post", post)
    store = demo_store()
    store.sandbox_launcher = SandboxManagerLauncher("http://manager.test/")
    assert await sweep(store) == {"suspended": 2, "terminated": 1, "removed": 3}
    assert asked == ["http://manager.test/internal/v1/sandboxes:reap"]


def test_a_sweep_leaves_a_computer_that_is_in_use(docker: _Docker) -> None:
    store = _store(docker)
    conversation = uuid.uuid4()
    _exec(store, conversation, "true")
    row = _row(store, conversation)
    _idle(store, row)
    # A tool call holds the scope: the sweep does not wait behind it or act under it.
    with runtime._held(store, row["tenant_id"], row["scope_key"]):
        assert reap_one(store, row) == ""
    assert row["status"] == "ready"
    # Used again before the sweep reads it: no longer due.
    row["last_active_at"] = utcnow()
    assert reap_one(store, row) == ""
    _idle(store, row)
    assert reap_one(store, row) == "suspend"
    assert reap_one(store, row) == ""


class _Valkey:
    """The two calls the scope lock makes, over a dict."""

    def __init__(self) -> None:
        self.keys: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        if nx and key in self.keys:
            return False
        self.keys[key] = value
        self.ttl[key] = ex
        return True

    def eval(self, _script: str, _count: int, key: str, token: str) -> int:
        if self.keys.get(key) == token:
            del self.keys[key]
            return 1
        return 0


async def test_one_process_at_a_time_holds_a_scope(settings: BaseServiceSettings) -> None:
    class _Process:
        valkey_client = _Valkey()

    process = _Process()
    tenant = uuid.uuid4()
    async with scope_lock(process, tenant, "conv:one"):
        key = f"ar:sbx:lock:{tenant}:conv:one"
        assert process.valkey_client.ttl[key] == settings.sandbox_lock_ttl_s
        # Another scope is free. The same scope is busy until it is let go.
        async with scope_lock(process, tenant, "conv:two"):
            pass
        with pytest.raises(SandboxBusyError):
            async with scope_lock(process, tenant, "conv:one"):
                pass
        assert key in process.valkey_client.keys
    assert not process.valkey_client.keys
    # A process with no Valkey is the only one that starts computers.
    async with scope_lock(object(), tenant, "conv:one"):
        pass


def test_a_container_is_labelled_with_its_install_tenant_and_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def start(image: str, name: str, **kwargs: Any) -> dict[str, object]:
        seen.update(kwargs, image=image, name=name)
        return {"container_id": "c1", "endpoint_url": _ENDPOINT, "token": kwargs["token"]}

    monkeypatch.setattr(sandbox_docker, "start_sandbox", start)
    launcher = DockerSandboxLauncher("image:1", install_id="inst", owner="host:7")
    launcher.start("ar-sbx-abc", "tok", sandbox_id="sbx", tenant_id="ten")
    assert seen["labels"] == {
        LABEL_PRODUCT: "true",
        LABEL_INSTALL: "inst",
        LABEL_OWNER: "host:7",
        LABEL_SANDBOX: "sbx",
        LABEL_TENANT: "ten",
    }


def test_the_daemon_is_asked_only_for_this_installs_labelled_containers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[dict[str, Any]] = []

    class _Listed:
        def __init__(self, info: dict[str, Any]) -> None:
            self._container = info

    class _Containers:
        async def list(self, **kwargs: Any) -> list[_Listed]:
            asked.append(kwargs)
            return [
                _Listed({"Id": "1", "Names": ["/ar-sbx-a"], "Labels": {"k": "v"}, "Created": 5}),
                _Listed({"Id": "2", "Names": ["/ar-sbx-b"], "Labels": {LABEL_PRODUCT: "true"}}),
                _Listed({"Id": "3", "Names": ["/not-ar-sbx-c"], "Labels": {}}),
            ]

    class _Client:
        containers = _Containers()

        async def close(self) -> None:
            return None

    import aiodocker

    monkeypatch.setattr(aiodocker, "Docker", _Client)
    launcher = DockerSandboxLauncher("image:1", install_id="inst", owner="host:7")
    listed = launcher.containers()
    assert asked[0] == {
        "all": True,
        "filters": {"label": [f"{LABEL_PRODUCT}=true", f"{LABEL_INSTALL}=inst"]},
    }
    assert listed[0] == {
        "container_id": "1",
        "name": "ar-sbx-a",
        "labels": {"k": "v"},
        "created": 5.0,
    }
    # Containers from before the labels are found by name, and only reported.
    assert launcher.unlabelled() == ["ar-sbx-a"]
    assert asked[1] == {"all": True, "filters": {"name": ["ar-sbx-"]}}
    # An install with no id lists nothing, so its sweep can remove nothing.
    assert DockerSandboxLauncher("image:1").containers() == []


def test_an_install_is_named_by_a_setting_or_by_its_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AR_INSTALL_ID", raising=False)
    monkeypatch.setenv("AR_DATABASE_URL", "postgresql+asyncpg://a:secret@db-one:5432/product")
    one = install_id(BaseServiceSettings())
    monkeypatch.setenv("AR_DATABASE_URL", "postgresql+asyncpg://b:other@db-one:5432/product")
    assert install_id(BaseServiceSettings()) == one
    monkeypatch.setenv("AR_DATABASE_URL", "postgresql+asyncpg://a:secret@db-two:5432/product")
    assert install_id(BaseServiceSettings()) != one
    assert "secret" not in one
    monkeypatch.setenv("AR_INSTALL_ID", "named")
    assert install_id(BaseServiceSettings()) == "named"


def _admin() -> Any:
    from ar_domain.agents.access import Actor
    from ar_domain.identity.permissions import PERMISSION_KEYS

    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)
