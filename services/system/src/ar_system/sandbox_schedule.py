"""The Temporal schedule that runs the sandbox sweep.

One schedule for the whole install starts ``SandboxReaperWorkflow`` every
``AR_SANDBOX_REAP_INTERVAL_S`` seconds. Every system worker asks for it as it starts;
asking again changes nothing but the interval, so any number of workers may ask.
"""

from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleUpdate,
)

SCHEDULE_ID = "sandbox-reaper"


def build_reaper_schedule(every_s: int) -> Schedule:
    """The sweep, every ``every_s`` seconds. A sweep still running is not started twice."""
    return Schedule(
        action=ScheduleActionStartWorkflow(
            "SandboxReaperWorkflow",
            id=SCHEDULE_ID,
            task_queue="ar-system",
        ),
        spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(seconds=every_s))]),
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
    )


async def ensure_reaper_schedule(client: Client, every_s: int) -> None:
    """Create the schedule, or bring an existing one to the configured interval."""
    schedule = build_reaper_schedule(every_s)
    try:
        await client.create_schedule(SCHEDULE_ID, schedule)
    except ScheduleAlreadyRunningError:
        handle = client.get_schedule_handle(SCHEDULE_ID)
        await handle.update(lambda _: ScheduleUpdate(schedule=schedule))
