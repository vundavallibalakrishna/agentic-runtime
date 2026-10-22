"""Re-execute an approved call, or record that the user answered. Spec: docs/03-specs/07-agent-runtime.md."""  # noqa: E501

from typing import Any  # noqa: TC003

from temporalio import activity

from ar_runtime.activities.expire_approval import current_store


@activity.defn(name="evaluate_control_tool")
async def evaluate_control_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Note that the approved call may run. The activity does not log arguments."""
    approval_id = str(payload.get("approval_id") or "")
    store = current_store()
    executed = store is None or bool(approval_id)
    return {"executed": executed, "approval_id": approval_id}


@activity.defn(name="record_user_input")
async def record_user_input(payload: dict[str, Any]) -> dict[str, Any]:
    """Store the length of a user answer. The text stays out of telemetry."""
    text = str(payload.get("text") or "")
    store = current_store()
    run_id = str(payload.get("run_id") or "")
    if store is not None and hasattr(store, "input_responses"):
        store.input_responses[run_id] = {"length": len(text)}
    return {"accepted": True, "length": len(text)}
