"""What a run tells its stream about the agents it calls.

One shape for every caller, the one in `ar_contracts.stream`: the chat draws a called
agent from these two events while the run goes, and from the saved call afterwards.
"""

from __future__ import annotations

SUMMARY_LIMIT = 2048
BRIEF_LIMIT = 500


def started(child: dict[str, object], task: str, call_id: str = "") -> dict[str, object]:
    return {
        "child_run_id": str(child.get("id") or ""),
        "agent_id": str(child.get("agent_id") or ""),
        "agent_name": str(child.get("agent_name") or child.get("agent_slug") or ""),
        "task_brief": task[:BRIEF_LIMIT],
        "call_id": call_id,
    }


def completed(
    child: dict[str, object],
    status: str,
    summary: str,
    usage: dict[str, object],
    call_id: str = "",
) -> dict[str, object]:
    return {
        "child_run_id": str(child.get("id") or ""),
        "status": status,
        "result_summary": summary[:SUMMARY_LIMIT],
        "usage": usage,
        "call_id": call_id,
    }


def called(outcome: dict[str, object], task: str) -> dict[str, object]:
    """One called agent as the chat shows it once the call is over."""
    return {
        "agent": str(outcome.get("name") or outcome.get("agent") or ""),
        "status": str(outcome.get("status") or ""),
        "task": task[:BRIEF_LIMIT],
        "summary": str(outcome.get("text") or "")[:SUMMARY_LIMIT],
        "child_run_id": str(outcome.get("child_id") or ""),
    }
