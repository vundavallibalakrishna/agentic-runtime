"""The runtime and system workers can share one process (small install, stage 2)."""

from __future__ import annotations

from ar_common import work


def test_the_launcher_finds_both_workers() -> None:
    runs = work.runners(["ar_runtime.worker", "ar_system.worker"])
    assert [run.__module__ for run in runs] == ["ar_runtime.worker", "ar_system.worker"]


def test_the_two_workers_poll_different_task_queues() -> None:
    from ar_runtime.main import TASK_QUEUE as RUNTIME
    from ar_system.main import TASK_QUEUE as SYSTEM
    from ar_system.workflows.eval_run import EVAL_QUEUE

    assert len({RUNTIME, SYSTEM, EVAL_QUEUE}) == 3


def test_compose_runs_them_as_one_service() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    text = (root / "compose.yaml").read_text(encoding="utf-8")
    assert '"ar_common.work", "ar_runtime.worker", "ar_system.worker"' in text
    split = (root / "compose.split-workers.yaml").read_text(encoding="utf-8")
    assert "runtime-worker:" in split
    assert "system-worker:" in split
