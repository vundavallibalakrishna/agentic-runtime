"""Temporal schedule action. The in-process ``:tick`` route stays the fallback.

A fire uses Temporal's clock. The workflow id includes the scheduled time so a
finished fire does not block the next one. ``POST /api/v1/routines/{id}:tick``
still runs the schedule inside this process when Temporal is not connected.
"""

from datetime import timedelta

from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
)


def schedule_workflow_id(routine_id: object) -> str:
    """One workflow per fire. Temporal fills ``ScheduledTime.Unix``."""
    return f"routine-fire-{routine_id}-{{{{.ScheduledTime.Unix}}}}"


def build_schedule(row: dict[str, object]) -> Schedule:
    """The schedule Temporal stores for one routine row."""
    raw_config = row.get("trigger_config")
    config = raw_config if isinstance(raw_config, dict) else {}
    routine_id = row.get("id")
    overlap = {
        "skip": ScheduleOverlapPolicy.SKIP,
        "buffer_one": ScheduleOverlapPolicy.BUFFER_ONE,
        "allow": ScheduleOverlapPolicy.ALLOW_ALL,
    }[str(row.get("concurrency_policy") or "skip")]
    return Schedule(
        action=ScheduleActionStartWorkflow(
            "RoutineRunWorkflow",
            {"routine_id": str(routine_id), "source": "schedule"},
            id=schedule_workflow_id(routine_id),
            task_queue="ar-system",
        ),
        spec=ScheduleSpec(
            cron_expressions=[str(config["cron"])],
            time_zone_name=str(config.get("timezone") or "UTC"),
            jitter=timedelta(seconds=int(config.get("jitter_s") or 0)),
        ),
        policy=SchedulePolicy(overlap=overlap),
        state=ScheduleState(paused=row.get("status") != "active"),
    )
