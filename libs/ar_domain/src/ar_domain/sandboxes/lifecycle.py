"""Keep a computer from outliving its use: the sweep, the orphan check and shutdown.

One sweep does three things. It suspends computers that have been idle and ends those
past their lifetime (``runtime.reap_one``). It removes containers that no computer owns
any more. It removes the folders such computers left on this host. Every mode runs the
same sweep: the system worker's schedule asks for it, the sandbox manager answers it
for an install that has one, and a process that starts containers itself runs it on a
timer (``SandboxKeeper``).
Spec: docs/03-specs/12-sandbox-manager.md §5.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ar_common.logging import get_logger
from ar_common.offload import run_sync
from ar_common.sandbox_docker import LABEL_INSTALL, LABEL_OWNER, LABEL_PRODUCT, LABEL_SANDBOX
from ar_common.settings import get_settings, install_id
from ar_domain.readmodel.model import RepositoryReadModel
from ar_domain.sandboxes import runtime
from ar_domain.sandboxes.manager_launch import SandboxManagerLauncher, owner_gone, process_owner

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path
    from typing import Any

_log = get_logger(__name__)

# A computer in one of these states owns no container.
_NO_CONTAINER = frozenset({"terminated", "failed", "suspended"})
# A computer in one of these states owns no folder on the host.
_NO_FOLDER = frozenset({"terminated", "failed"})
# Compare-and-delete: a lock is released only by the process that took it.
_RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end"
_reported: set[str] = set()


class SandboxBusyError(RuntimeError):
    """Another process holds this computer's scope and did not let go in time."""


@asynccontextmanager
async def scope_lock(process_store: Any, tenant_id: object, scope_key: str) -> AsyncIterator[None]:
    """Hold one computer's scope across every process of the install.

    The lock is a Valkey key, taken before the tenant's rows are loaded, so whoever holds
    it reads the row as the last holder left it. It expires after
    ``AR_SANDBOX_LOCK_TTL_S`` should its holder die. A process with no Valkey is the only
    one that starts computers, and the lock inside ``runtime`` is enough for it.
    """
    client = getattr(process_store, "valkey_client", None)
    if client is None:
        yield
        return
    settings = get_settings()
    key = f"ar:sbx:lock:{tenant_id}:{scope_key}"
    token = uuid.uuid4().hex
    deadline = time.monotonic() + settings.sandbox_ensure_timeout_s
    while not await asyncio.to_thread(
        client.set, key, token, nx=True, ex=settings.sandbox_lock_ttl_s
    ):
        if time.monotonic() >= deadline:
            raise SandboxBusyError("the computer is busy starting or pausing; try again")
        await asyncio.sleep(0.2)
    try:
        yield
    finally:
        with contextlib.suppress(Exception):  # an expired lock is already released
            await asyncio.to_thread(client.eval, _RELEASE, 1, key, token)


def orphans(
    containers: list[dict[str, object]],
    states: dict[str, str],
    *,
    install: str,
    me: str,
    shared_rows: bool,
    now: float,
    grace_s: float,
) -> list[dict[str, object]]:
    """The containers nobody owns, out of those the daemon listed for this install.

    A container is an orphan when its computer has no row, or the row says the computer
    is terminated, failed or suspended. One younger than ``grace_s`` is never an orphan:
    its row may not be saved yet. A container without the product label or with another
    install's id is never an orphan, whatever was listed.

    ``shared_rows`` says the rows are in the database every process reads. When they
    are in this process only, a container with no row here may belong to another process
    of the install that is still running, so it is an orphan only when this process
    started it or its starter is gone.
    """
    found: list[dict[str, object]] = []
    for item in containers:
        raw = item.get("labels")
        labels = raw if isinstance(raw, dict) else {}
        if (
            labels.get(LABEL_PRODUCT) != "true"
            or not install
            or labels.get(LABEL_INSTALL) != install
        ):
            continue
        created = item.get("created")
        if not isinstance(created, (int, float)) or now - created < grace_s:
            continue
        status = states.get(str(labels.get(LABEL_SANDBOX) or ""))
        if status is None and not shared_rows:
            owner = str(labels.get(LABEL_OWNER) or "")
            if owner != me and not owner_gone(owner):
                continue
        if status is None or status in _NO_CONTAINER:
            found.append(item)
    return found


def _folders(install: str) -> list[tuple[str, str, Path]]:
    """Host folders this install made: ``(sandbox id, owner, path)``. Others are skipped."""
    root = runtime.host_root()
    found: list[tuple[str, str, Path]] = []
    if not root.is_dir():
        return found
    for path in root.iterdir():
        mark = path / runtime.FOLDER_MARK
        try:
            uuid.UUID(path.name)
            lines = mark.read_text(encoding="utf-8").splitlines()
        except ValueError, OSError:
            continue
        if lines and lines[0] == install:
            found.append((path.name, lines[1] if len(lines) > 1 else "", path))
    return found


def _survey(launcher: object, install: str) -> tuple[list[dict[str, object]], list[Any], list[str]]:
    """What is on this host: the install's containers, its folders, and unlabelled leftovers."""
    list_containers = getattr(launcher, "containers", None)
    list_unlabelled = getattr(launcher, "unlabelled", None)
    containers = list_containers() if callable(list_containers) else []
    legacy = list_unlabelled() if callable(list_unlabelled) else []
    return containers, _folders(install), legacy


def _remove(launcher: object, containers: list[dict[str, object]], folders: list[Path]) -> None:
    stop = getattr(launcher, "stop", None)
    for item in containers:
        if callable(stop):
            stop(str(item.get("container_id") or ""))
        _log.info("sandbox_orphan_removed", container=str(item.get("name") or ""))
    for path in folders:
        shutil.rmtree(path, ignore_errors=True)


async def reconcile(process_store: Any) -> int:
    """Remove this install's containers and host folders that no computer owns.

    Returns how many containers were removed. Containers named ``ar-sbx-*`` with no label
    come from a release before the labels; they are reported once and never removed.
    """
    launcher = getattr(process_store, "sandbox_launcher", None)
    if isinstance(launcher, SandboxManagerLauncher):
        return 0
    settings = get_settings()
    install = install_id(settings)
    containers, folders, legacy = await asyncio.to_thread(_survey, launcher, install)
    fresh = sorted(set(legacy) - _reported)
    if fresh:
        _reported.update(fresh)
        _log.warning("sandbox_unlabelled_containers", count=len(fresh), names=fresh)
    shared = isinstance(process_store, RepositoryReadModel)
    states = await _states(process_store, containers, folders)
    now = time.time()
    grace = float(settings.sandbox_orphan_grace_s)
    me = process_owner()
    gone = orphans(
        containers, states, install=install, me=me, shared_rows=shared, now=now, grace_s=grace
    )
    stale: list[Path] = []
    for sandbox_id, owner, path in folders:
        status = states.get(sandbox_id)
        with contextlib.suppress(OSError):
            if now - path.stat().st_mtime < grace:
                continue
            if status is None and not shared and owner != me and not owner_gone(owner):
                continue
            if status is None or status in _NO_FOLDER:
                stale.append(path)
    if gone or stale:
        await asyncio.to_thread(_remove, launcher, gone, stale)
    return len(gone)


async def _states(
    process_store: Any, containers: list[dict[str, object]], folders: list[Any]
) -> dict[str, str]:
    """The status of every computer a container or a folder names. No row, no entry."""
    if not isinstance(process_store, RepositoryReadModel):
        return {str(key): str(row.get("status")) for key, row in process_store.sandboxes.items()}
    named: set[uuid.UUID] = set()
    for item in containers:
        raw = item.get("labels")
        label = raw.get(LABEL_SANDBOX) if isinstance(raw, dict) else None
        with contextlib.suppress(ValueError):
            named.add(uuid.UUID(str(label)))
    for sandbox_id, _owner, _path in folders:
        named.add(uuid.UUID(sandbox_id))
    found = await process_store.sandbox_states(sorted(named, key=str))
    return {str(key): status for key, status in found.items()}


async def _reap_shared(model: RepositoryReadModel) -> dict[str, int]:
    """Reap an install whose rows are in the database, one due computer at a time.

    The scope is locked first and the tenant loaded after, so two replicas sweeping at
    once, or a sweep and a tool call, each see what the other saved.
    """
    done = {"suspended": 0, "terminated": 0}
    for tenant_id, sandbox_id, scope_key in await model.sandboxes_due():
        try:
            async with scope_lock(model, tenant_id, scope_key), model.open(tenant_id) as unit:
                row = unit.sandboxes.get(sandbox_id)
                action = await run_sync(runtime.reap_one, unit, row) if row is not None else ""
        except SandboxBusyError:
            continue
        except Exception as exc:  # noqa: BLE001 - one computer must not stop the sweep
            _log.warning(
                "sandbox_reap_failed", sandbox_id=str(sandbox_id), error=type(exc).__name__
            )
            continue
        if action == "suspend":
            done["suspended"] += 1
        elif action == "terminate":
            done["terminated"] += 1
    return done


async def sweep(process_store: Any) -> dict[str, int]:
    """One pass: suspend the idle, end the expired, remove what nobody owns.

    A process that gets its computers from the sandbox manager asks the manager, which
    is where the containers are. Any other process does the work itself. Repeating a pass
    is safe: a computer already suspended or ended is not due, and removing a container
    that is gone is not an error.
    """
    launcher = getattr(process_store, "sandbox_launcher", None)
    if isinstance(launcher, SandboxManagerLauncher):
        asked = await run_sync(launcher.reap)
        return {key: int(asked.get(key, 0)) for key in ("suspended", "terminated", "removed")}
    if isinstance(process_store, RepositoryReadModel):
        done = await _reap_shared(process_store)
    else:
        done = await run_sync(runtime.reap, process_store)
    done["removed"] = await reconcile(process_store)
    return done


def stop_started(store: Any) -> int:
    """End every computer whose container this process started. Returns how many.

    A process that keeps its rows in memory calls this as it stops: the rows go with the
    process, so the containers must too. Each is ended through the ordinary terminate
    path, which records it.
    """
    launcher = getattr(store, "sandbox_launcher", None)
    if launcher is None or isinstance(launcher, SandboxManagerLauncher):
        return 0
    ended = 0
    for row in list(store.sandboxes.values()):
        if row.get("status") in _NO_CONTAINER or not row.get("endpoint_url"):
            continue
        runtime.terminate_row(store, row, actor=row.get("user_id"))
        ended += 1
    return ended


def _stop_mine(launcher: object) -> None:
    """Remove the containers this very process started, whether or not a row still names them."""
    list_containers = getattr(launcher, "containers", None)
    stop = getattr(launcher, "stop", None)
    if not callable(list_containers) or not callable(stop):
        return
    me = process_owner()
    for item in list_containers():
        raw = item.get("labels")
        if isinstance(raw, dict) and raw.get(LABEL_OWNER) == me:
            stop(str(item.get("container_id") or ""))


class SandboxKeeper:
    """Runs the sweep on a timer in a process that starts computers itself.

    The interval is ``AR_SANDBOX_REAP_INTERVAL_S``. ``stop`` cancels the timer and ends
    the computers this process started, so a clean restart leaves no container behind.
    """

    def __init__(self, store: Any, *, interval_s: float) -> None:
        self.store = store
        self.interval_s = interval_s
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Begin sweeping. A second call does nothing."""
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(self._run())

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_s)
            try:
                await sweep(self.store)
            except Exception as exc:  # noqa: BLE001 - one failed pass must not end the timer
                _log.warning("sandbox_sweep_failed", error=type(exc).__name__)

    async def stop(self) -> None:
        """Stop sweeping and end this process's computers."""
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await run_sync(stop_started, self.store)
        launcher = getattr(self.store, "sandbox_launcher", None)
        await asyncio.to_thread(_stop_mine, launcher)
        from ar_domain.durable.flush import flush_store  # noqa: PLC0415

        with contextlib.suppress(Exception):  # the process is leaving; nothing can retry
            await flush_store(self.store)


@asynccontextmanager
async def keeping(store: Any) -> AsyncIterator[None]:
    """Sweep for as long as the block lasts, and end this process's computers after it.

    Every process that may start computers wraps its serving in this. Where the process
    has nothing to keep (``keeper_for``) the block runs as it is.
    """
    keeper = keeper_for(store)
    if keeper is not None:
        keeper.start()
    try:
        yield
    finally:
        if keeper is not None:
            await keeper.stop()


def keeper_for(store: Any) -> SandboxKeeper | None:
    """The keeper for a process that holds its own computers, or ``None``.

    A process that asks the sandbox manager has nothing to keep. Neither has one whose
    rows are in the database: the system worker's schedule drives its sweep, and its
    computers outlive a restart.
    """
    launcher = getattr(store, "sandbox_launcher", None)
    if isinstance(launcher, SandboxManagerLauncher) or isinstance(store, RepositoryReadModel):
        return None
    return SandboxKeeper(store, interval_s=float(get_settings().sandbox_reap_interval_s))
