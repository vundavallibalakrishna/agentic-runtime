"""Production-cert defect 9: deleting the last file in a turn sticks.

A conversation shows one working folder: the next turn restores the latest turn's files.
When a turn deleted its last file its saved rows were pruned to none, so the next turn
fell back to an earlier run that still held the file and brought it back. A tombstone now
records the emptied folder so the deletion carries forward. Proof: unit.
"""

import uuid
from pathlib import Path

from ar_domain.chat.service import demo_id
from ar_domain.durability.store import (
    clear_workspace_dir,
    restore_workspace,
    snapshot_workspace,
    workspace_root,
)
from ar_testing.demo import demo_store


def _run(
    store: object, run_id: uuid.UUID, conversation_id: uuid.UUID, tenant: uuid.UUID, order: str
) -> None:
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "status": "completed",
        "created_at": order,
    }


def _workspace(run_id: uuid.UUID) -> Path:
    return workspace_root(run_id) / "workspace"


def _restore(
    store: object, run_id: uuid.UUID, conversation_id: uuid.UUID, tenant: uuid.UUID
) -> None:
    restore_workspace(
        store,
        {"_run_id": run_id, "_tenant_id": tenant, "_conversation_id": conversation_id},
    )


def test_deleting_the_last_file_sticks_across_turns() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    conv = uuid.uuid4()
    first, second, third = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        _run(store, first, conv, tenant, "1")
        _run(store, second, conv, tenant, "2")
        _run(store, third, conv, tenant, "3")

        # Turn 1 writes a file.
        (_workspace(first) / "outputs").mkdir(parents=True, exist_ok=True)
        (_workspace(first) / "outputs" / "report.csv").write_bytes(b"a,b\n1,2\n")
        snapshot_workspace(store, first, tenant)

        # Turn 2 inherits it, then deletes the last file.
        _restore(store, second, conv, tenant)
        assert (_workspace(second) / "outputs" / "report.csv").is_file()
        (_workspace(second) / "outputs" / "report.csv").unlink()
        snapshot_workspace(store, second, tenant)

        # Turn 3 must not see the deleted file.
        _restore(store, third, conv, tenant)
        assert not (_workspace(third) / "outputs" / "report.csv").exists()
    finally:
        for run_id in (first, second, third):
            clear_workspace_dir(run_id)


def test_a_turn_that_keeps_the_file_still_restores_it() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    conv = uuid.uuid4()
    first, second, third = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        _run(store, first, conv, tenant, "1")
        _run(store, second, conv, tenant, "2")
        _run(store, third, conv, tenant, "3")

        (_workspace(first) / "outputs").mkdir(parents=True, exist_ok=True)
        (_workspace(first) / "outputs" / "report.csv").write_bytes(b"x")
        snapshot_workspace(store, first, tenant)

        # Turn 2 inherits and keeps the file.
        _restore(store, second, conv, tenant)
        snapshot_workspace(store, second, tenant)

        # Turn 3 still sees it: an untouched turn does not hide earlier work.
        _restore(store, third, conv, tenant)
        assert (_workspace(third) / "outputs" / "report.csv").is_file()
    finally:
        for run_id in (first, second, third):
            clear_workspace_dir(run_id)
