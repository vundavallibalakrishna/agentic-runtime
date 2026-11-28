"""Temporal worker entry. The health server stays up when Temporal is down."""

import asyncio

from temporalio.client import Client

from ar_common.host_ports import local_endpoint
from ar_common.logging import get_logger
from ar_common.settings import get_settings, loopback_allowed
from ar_common.temporal_worker import temporal_unavailable_fields, temporal_worker_kwargs

_log = get_logger(__name__)


def _address() -> str:
    settings = get_settings()
    configured = str(getattr(settings, "temporal_address", "") or "").strip()
    if configured:
        return configured
    return local_endpoint("AR_TEMPORAL_ADDRESS", "localhost:{port}", "AR_TEMPORAL_HOST_PORT")


async def _prepare_store() -> object:
    from ar_domain.chat.service import ChatService  # noqa: PLC0415
    from ar_domain.durable.bind import attach_store  # noqa: PLC0415
    from ar_domain.pii.analyzer import warm  # noqa: PLC0415
    from ar_domain.readmodel.boot import build_product_store  # noqa: PLC0415
    from ar_system.routines_store import bind_store as bind_routines  # noqa: PLC0415
    from ar_system.workflows.sandbox_reaper import bind_store as bind_sandboxes  # noqa: PLC0415

    settings = get_settings()
    store = build_product_store(
        settings,
        allow_loopback=loopback_allowed(settings),
    )
    # A routine's tool calls run here. The engine that masks their results is built now.
    await warm()
    if isinstance(store, ChatService):
        await attach_store(store, settings.database_url)
    bind_routines(store)
    bind_sandboxes(store)
    return store


async def _sweep_while_connected(store: object, sweep: object) -> None:
    from ar_common.settings import get_settings  # noqa: PLC0415

    while True:
        try:
            await sweep(store)  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001 — one failed sweep must not stop the worker
            _log.warning("webhook_sweep_failed", error=type(exc).__name__)
        await asyncio.sleep(max(5, int(get_settings().webhook_sweep_grace_s)))


async def run_worker() -> None:
    """Connect and poll ``ar-system``. Failures are logged and retried."""
    from temporalio.worker import Worker  # noqa: PLC0415

    from ar_system.main import TASK_QUEUE  # noqa: PLC0415
    from ar_system.workflows.eval_run import (  # noqa: PLC0415
        EVAL_ACTIVITIES,
        EVAL_QUEUE,
        EvalRunWorkflow,
    )
    from ar_system.workflows.routine_poll import RoutinePollWorkflow, poll_activity  # noqa: PLC0415
    from ar_system.workflows.routine_run import (  # noqa: PLC0415
        RoutineDeliveryWorkflow,
        RoutineReconcileWorkflow,
        RoutineRunWorkflow,
        accept_activity,
        complete_activity,
        prepare_activity,
        reconcile_activity,
        release_activity,
    )
    from ar_system.workflows.sandbox_reaper import SandboxReaperWorkflow, reap_sandboxes  # noqa: PLC0415
    from ar_system.workflows.summary_refresh import (  # noqa: PLC0415
        ConversationSummaryWorkflow,
        refresh_conversation_summary,
    )
    from ar_system.workflows.webhook_run import (  # noqa: PLC0415
        WebhookDeliveryWorkflow,
        deliver_webhook_activity,
    )

    store: object | None = None
    while True:
        try:
            if store is None:
                store = await _prepare_store()
            client = await asyncio.wait_for(
                Client.connect(
                    _address(),
                    namespace=getattr(get_settings(), "temporal_namespace", "") or "default",
                ),
                timeout=5,
            )
            store.temporal_client = client  # type: ignore[attr-defined]
            from ar_system.sandbox_schedule import ensure_reaper_schedule  # noqa: PLC0415

            await ensure_reaper_schedule(client, get_settings().sandbox_reap_interval_s)
            worker = Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=[
                    SandboxReaperWorkflow,
                    RoutineRunWorkflow,
                    RoutineDeliveryWorkflow,
                    RoutinePollWorkflow,
                    RoutineReconcileWorkflow,
                    ConversationSummaryWorkflow,
                    WebhookDeliveryWorkflow,
                ],
                activities=[
                    reap_sandboxes,
                    accept_activity,
                    prepare_activity,
                    complete_activity,
                    release_activity,
                    poll_activity,
                    reconcile_activity,
                    refresh_conversation_summary,
                    deliver_webhook_activity,
                ],
                **temporal_worker_kwargs(),
            )
            eval_worker = Worker(
                client,
                task_queue=EVAL_QUEUE,
                workflows=[EvalRunWorkflow],
                activities=EVAL_ACTIVITIES,
                **temporal_worker_kwargs(),
            )
            _log.info("temporal_connected", queue=TASK_QUEUE)
            from ar_domain.sandboxes.lifecycle import keeping  # noqa: PLC0415
            from ar_domain.webhooks.delivery import sweep_due_deliveries  # noqa: PLC0415

            # A worker that starts computers itself ends them as it stops.
            # The sweep also runs while Temporal is up, for deliveries the workflow did not finish.
            async with keeping(store):
                sweep = asyncio.create_task(_sweep_while_connected(store, sweep_due_deliveries))
                try:
                    await asyncio.gather(worker.run(), eval_worker.run())
                finally:
                    sweep.cancel()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep the health server up
            _log.warning("temporal_unavailable", **temporal_unavailable_fields(_address(), exc))
            if store is not None:
                store.temporal_client = None  # type: ignore[attr-defined]
                from ar_domain.webhooks.delivery import sweep_due_deliveries  # noqa: PLC0415

                await sweep_due_deliveries(store)
            await asyncio.sleep(5)
