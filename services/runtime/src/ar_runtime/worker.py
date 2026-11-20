"""Poll ``ar-runtime`` for turns, delegation, approvals and tool calls."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

from temporalio.client import Client
from temporalio.worker import Worker

from ar_common.host_ports import local_endpoint
from ar_common.logging import get_logger
from ar_common.settings import fake_models_allowed, get_settings, loopback_allowed
from ar_common.temporal_worker import temporal_unavailable_fields, temporal_worker_kwargs
from ar_runtime.activities.advance_chat_step import advance_chat_step
from ar_runtime.activities.create_child_run import create_child_run
from ar_runtime.activities.execute_chat_turn import execute_chat_turn, finish_chat_turn
from ar_runtime.activities.expire_approval import bind_store, cancel_approval, expire_approval
from ar_runtime.activities.research_step import (
    research_cancel,
    research_exhausted,
    research_step,
    research_subtask,
)
from ar_runtime.activities.start_run import start_run
from ar_runtime.main import TASK_QUEUE
from ar_runtime.workflows.delegation import AgentRunWorkflow, ChildRunWorkflow
from ar_runtime.workflows.research import ResearchSubtaskWorkflow, ResearchWorkflow
from ar_runtime.workflows.tool_turn import ToolTurnWorkflow
from ar_runtime.workflows.turn import TurnWorkflow

_log = get_logger(__name__)


def runtime_workflows() -> list[type]:
    """Workflows the runtime worker polls. Tests register this same list."""
    return [
        TurnWorkflow,
        AgentRunWorkflow,
        ChildRunWorkflow,
        ToolTurnWorkflow,
        ResearchWorkflow,
        ResearchSubtaskWorkflow,
    ]


def runtime_activities() -> list[Callable[..., Any]]:
    """Activities the runtime worker polls. Tests register this same list."""
    return [
        execute_chat_turn,
        advance_chat_step,
        finish_chat_turn,
        research_step,
        research_subtask,
        research_cancel,
        research_exhausted,
        start_run,
        create_child_run,
        expire_approval,
        cancel_approval,
    ]


def _address() -> str:
    settings = get_settings()
    configured = str(getattr(settings, "temporal_address", "") or "").strip()
    if configured:
        return configured
    return local_endpoint("AR_TEMPORAL_ADDRESS", "localhost:{port}", "AR_TEMPORAL_HOST_PORT")


async def _prepare_store() -> object:
    from ar_domain.chat.service import ChatService  # noqa: PLC0415
    from ar_domain.durable.bind import attach_store  # noqa: PLC0415
    from ar_domain.pii.analyzer import warm_up  # noqa: PLC0415
    from ar_domain.readmodel.boot import build_product_store  # noqa: PLC0415

    settings = get_settings()
    store = build_product_store(
        settings,
        allow_loopback=loopback_allowed(settings),
        fake_models_allowed=fake_models_allowed(settings.env),
    )
    store.model_gateway_url = str(getattr(settings, "model_gateway_url", "") or "")
    from ar_domain.tools.gateway_client import configure_gateway  # noqa: PLC0415

    configure_gateway(store, env=str(getattr(settings, "env", "dev")))
    # Tool calls run here. The engine that masks their results is built now, not in the
    # first call.
    warm_up()
    if isinstance(store, ChatService):
        await attach_store(store, settings.database_url)
    bind_store(store)
    return store


async def run_worker() -> None:
    """Connect and poll. A down frontend is logged and retried."""
    while True:
        try:
            client = await asyncio.wait_for(
                Client.connect(
                    _address(),
                    namespace=getattr(get_settings(), "temporal_namespace", "") or "default",
                ),
                timeout=5,
            )
            store = await _prepare_store()
            worker = Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=runtime_workflows(),
                activities=runtime_activities(),
                **temporal_worker_kwargs(),
            )
            _log.info("temporal_connected", queue=TASK_QUEUE)
            from ar_domain.sandboxes.lifecycle import keeping  # noqa: PLC0415

            # A worker that starts computers itself sweeps them and ends them as it stops.
            async with keeping(store):
                await worker.run()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep the health server up
            _log.warning("temporal_unavailable", **temporal_unavailable_fields(_address(), exc))
            await asyncio.sleep(5)
