"""Temporal worker entry. The health server stays up when Temporal is down."""

import asyncio

from temporalio.client import Client

from ar_common.host_ports import local_endpoint
from ar_common.logging import get_logger
from ar_common.settings import get_settings

_log = get_logger(__name__)


def _address() -> str:
    settings = get_settings()
    configured = str(getattr(settings, "temporal_address", "") or "").strip()
    if configured:
        return configured
    return local_endpoint("AR_TEMPORAL_ADDRESS", "localhost:{port}", "AR_TEMPORAL_HOST_PORT")


async def _prepare_store() -> None:
    from ar_domain.chat.service import ChatService  # noqa: PLC0415
    from ar_domain.durable.bind import bind_store  # noqa: PLC0415
    from ar_system.routines_store import bind_store as bind_routines  # noqa: PLC0415
    from ar_system.workflows.memory_extraction import bind_store as bind_memory  # noqa: PLC0415
    from ar_system.workflows.sandbox_reaper import bind_store as bind_sandboxes  # noqa: PLC0415

    settings = get_settings()
    store = ChatService(allow_loopback=True)
    await bind_store(store, settings.database_url)
    bind_routines(store)
    bind_memory(store)
    bind_sandboxes(store)


async def run_worker() -> None:
    """Connect and poll ``ar-system``. Failures are logged and retried."""
    from temporalio.worker import Worker  # noqa: PLC0415

    from ar_system.main import TASK_QUEUE  # noqa: PLC0415
    from ar_system.workflows.memory_extraction import (  # noqa: PLC0415
        MemoryExtractionWorkflow,
        extract_memory,
    )
    from ar_system.workflows.routine_poll import RoutinePollWorkflow, poll_activity  # noqa: PLC0415
    from ar_system.workflows.routine_run import (  # noqa: PLC0415
        RoutineReconcileWorkflow,
        RoutineRunWorkflow,
        accept_activity,
        complete_activity,
        prepare_activity,
        reconcile_activity,
    )
    from ar_system.workflows.sandbox_reaper import SandboxReaperWorkflow, reap_sandboxes  # noqa: PLC0415

    while True:
        try:
            client = await asyncio.wait_for(
                Client.connect(
                    _address(),
                    namespace=getattr(get_settings(), "temporal_namespace", "") or "default",
                ),
                timeout=5,
            )
            await _prepare_store()
            worker = Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=[
                    SandboxReaperWorkflow,
                    MemoryExtractionWorkflow,
                    RoutineRunWorkflow,
                    RoutinePollWorkflow,
                    RoutineReconcileWorkflow,
                ],
                activities=[
                    reap_sandboxes,
                    extract_memory,
                    accept_activity,
                    prepare_activity,
                    complete_activity,
                    poll_activity,
                    reconcile_activity,
                ],
            )
            _log.info("temporal_connected", queue=TASK_QUEUE)
            await worker.run()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep the health server up
            _log.warning("temporal_unavailable", error=type(exc).__name__)
            await asyncio.sleep(5)
