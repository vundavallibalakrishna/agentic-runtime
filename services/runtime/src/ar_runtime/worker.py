"""Poll ``ar-runtime`` for turns, delegation, approvals and tool calls."""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from ar_common.host_ports import local_endpoint
from ar_common.logging import get_logger
from ar_common.settings import get_settings
from ar_runtime.activities.create_child_run import create_child_run
from ar_runtime.activities.evaluate_control_tool import evaluate_control_tool, record_user_input
from ar_runtime.activities.execute_chat_turn import execute_chat_turn
from ar_runtime.activities.expire_approval import bind_store, cancel_approval, expire_approval
from ar_runtime.main import TASK_QUEUE
from ar_runtime.workflows.approval_wait import ApprovalWaitWorkflow
from ar_runtime.workflows.delegation import AgentRunWorkflow, ChildRunWorkflow
from ar_runtime.workflows.tool_turn import ToolTurnWorkflow
from ar_runtime.workflows.turn import TurnWorkflow

_log = get_logger(__name__)


def _address() -> str:
    settings = get_settings()
    configured = str(getattr(settings, "temporal_address", "") or "").strip()
    if configured:
        return configured
    return local_endpoint("AR_TEMPORAL_ADDRESS", "localhost:{port}", "AR_TEMPORAL_HOST_PORT")


async def _prepare_store() -> None:
    from ar_domain.chat.service import ChatService  # noqa: PLC0415
    from ar_domain.durable.bind import bind_store as bind_durable  # noqa: PLC0415

    settings = get_settings()
    store = ChatService(allow_loopback=True)
    store.model_gateway_url = str(getattr(settings, "model_gateway_url", "") or "")
    await bind_durable(store, settings.database_url)
    bind_store(store)


async def run_worker() -> None:
    """Connect and poll. A down frontend is logged and retried."""
    while True:
        try:
            client = await asyncio.wait_for(Client.connect(_address()), timeout=0.5)
            await _prepare_store()
            worker = Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=[
                    TurnWorkflow,
                    AgentRunWorkflow,
                    ChildRunWorkflow,
                    ApprovalWaitWorkflow,
                    ToolTurnWorkflow,
                ],
                activities=[
                    execute_chat_turn,
                    create_child_run,
                    expire_approval,
                    cancel_approval,
                    evaluate_control_tool,
                    record_user_input,
                ],
            )
            _log.info("temporal_connected", queue=TASK_QUEUE)
            await worker.run()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep the health server up
            _log.warning("temporal_unavailable", error=type(exc).__name__)
            await asyncio.sleep(5)
