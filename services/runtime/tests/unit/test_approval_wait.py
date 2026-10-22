"""Time-skipping approval and user-input waits."""

import uuid
from datetime import timedelta

import pytest
from temporalio.worker import Worker

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.chat.service import ChatService
from ar_runtime.activities.evaluate_control_tool import evaluate_control_tool, record_user_input
from ar_runtime.activities.expire_approval import bind_store, cancel_approval, expire_approval
from ar_runtime.workflows.agent_run import approval_wait_workflow
from ar_runtime.workflows.approval_wait import ApprovalWaitWorkflow

pytestmark = pytest.mark.asyncio


async def _start(env: object, payload: dict[str, object], name: str) -> object:
    client = env.client  # type: ignore[attr-defined]
    return await client.start_workflow(
        ApprovalWaitWorkflow.run,
        payload,
        id=name,
        task_queue="m5-approvals",
    )


async def test_approval_wait_approves_rejects_expires_cancels_and_accepts_input(
    temporal_env: object,
) -> None:
    assert approval_wait_workflow() is ApprovalWaitWorkflow
    store = ChatService()
    approval_id = new_id()
    store.approvals[approval_id] = {
        "id": approval_id,
        "tenant_id": uuid.uuid4(),
        "status": "pending",
        "run_id": None,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    bind_store(store)
    client = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        client,
        task_queue="m5-approvals",
        workflows=[ApprovalWaitWorkflow],
        activities=[expire_approval, cancel_approval, evaluate_control_tool, record_user_input],
    ):
        approved = await _start(
            temporal_env,
            {"kind": "approval", "approval_id": str(approval_id), "wait_s": 86400},
            "m5-approve",
        )
        await approved.signal(ApprovalWaitWorkflow.approval_decided, {"status": "approved"})
        assert (await approved.result())["status"] == "completed"

        rejected = await _start(
            temporal_env, {"kind": "approval", "approval_id": "r", "wait_s": 86400}, "m5-reject"
        )
        await rejected.signal(
            ApprovalWaitWorkflow.approval_decided, {"status": "rejected", "reason": "not this"}
        )
        rejection = await rejected.result()
        assert rejection["status"] == "rejected"
        assert rejection["reason"] == "not this"

        expiring = new_id()
        store.approvals[expiring] = {
            "id": expiring,
            "tenant_id": store.approvals[approval_id]["tenant_id"],
            "status": "pending",
            "run_id": None,
            "created_at": utcnow(),
        }
        expired = await _start(
            temporal_env,
            {"kind": "approval", "approval_id": str(expiring), "wait_s": 86400},
            "m5-expire",
        )
        await temporal_env.sleep(timedelta(seconds=86401))  # type: ignore[attr-defined]
        assert (await expired.result())["status"] == "expired"
        assert store.approvals[expiring]["status"] == "expired"

        cancelling = new_id()
        store.approvals[cancelling] = {
            "id": cancelling,
            "tenant_id": store.approvals[approval_id]["tenant_id"],
            "status": "pending",
            "run_id": None,
            "created_at": utcnow(),
        }
        cancelled = await _start(
            temporal_env,
            {"kind": "approval", "approval_id": str(cancelling), "wait_s": 86400},
            "m5-cancel",
        )
        await cancelled.signal(ApprovalWaitWorkflow.cancel_wait)
        assert (await cancelled.result())["status"] == "cancelled"
        assert store.approvals[cancelling]["status"] == "cancelled"

        answered = await _start(
            temporal_env, {"kind": "input", "run_id": "run-1", "wait_s": 60}, "m5-input"
        )
        await answered.signal(ApprovalWaitWorkflow.user_input, {"text": "blue"})
        answer = await answered.result()
        assert answer["status"] == "completed"
        assert answer["length"] == 4
        assert store.input_responses["run-1"]["length"] == 4
