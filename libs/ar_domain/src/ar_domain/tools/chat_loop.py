"""The approval pause for a chat turn.

The agent loop (``tools.agent_loop``) calls :func:`_pause` when a tool needs approval
before it runs, so the run waits for a reviewer and resumes through the path the worker
uses. The in-process keyword tool turn that used to live here is gone (M38a-T04): the model
decides every tool call through the agent loop.
"""

import uuid
from typing import TYPE_CHECKING

from ar_domain.approvals.pending import hold
from ar_domain.tools.logic import call_args_hash

if TYPE_CHECKING:
    from typing import Any


def _policy_hash(result: dict[str, object]) -> object:
    policy = result.get("policy")
    if isinstance(policy, dict):
        return policy.get("args_hash")
    return None


def _pause(  # noqa: PLR0917
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    call: dict[str, Any],
    result: dict[str, object],
    arguments: dict[str, object],
) -> None:
    run["status"] = "waiting_approval"
    pending: dict[str, object] = {
        "approval_id": uuid.UUID(str(result.get("approval_id"))),
        "tool_version_id": call["tool_version_id"],
        "arguments": arguments,
        "args_hash": _policy_hash(result)
        or call_args_hash(str(call["tool_version_id"]), arguments),
        "model_call_id": result.get("tool_call_id"),
    }
    # The hash the pipeline stored is the one on the approval, not the model id.
    approval = result.get("approval")
    if isinstance(approval, dict) and approval.get("id"):
        row = store.approvals.get(uuid.UUID(str(approval["id"])))
        if isinstance(row, dict):
            pending["args_hash"] = row.get("args_hash")
            pending["model_call_id"] = row.get("tool_call_id")
            pending["tool_call_id"] = row.get("tool_call_id")
    # Kept with the run, so the request that takes the decision can continue it.
    hold(run, pending)
    text = "Waiting for approval before this tool runs."
    assistant["text"] = text
    assistant["content"] = [{"type": "text", "text": text}]
    assistant["status"] = "streaming"
    assistant["tool_calls"] = [
        {
            "qualified_name": call["qualified_name"],
            "status": "awaiting_approval",
            "arguments": arguments,
            "result_preview": text,
            "approval_id": str(result.get("approval_id") or ""),
        }
    ]
    store._emit(
        run,
        "tool_call.approval_required",
        {
            "tool_call_id": str(result.get("tool_call_id") or ""),
            "approval_id": str(result.get("approval_id") or ""),
            "qualified_name": call["qualified_name"],
            "risk_class": call["risk_class"],
            "text": text,
            "result_preview": text,
        },
    )
    store._emit(run, "run.status", {"status": "waiting_approval"})
