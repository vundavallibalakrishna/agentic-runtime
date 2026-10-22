"""Parent and child agent runs. Spec: docs/02-architecture/request-flows.md §7."""

import asyncio
from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import workflow
from temporalio.workflow import ParentClosePolicy

with workflow.unsafe.imports_passed_through():
    from ar_domain.skills.logic import budget_exhausted
    from ar_runtime.activities.create_child_run import create_child_run


@workflow.defn
class ChildRunWorkflow:
    """One delegated run. An approval signal unblocks a waiting child."""

    def __init__(self) -> None:
        self.decision: dict[str, Any] | None = None

    @workflow.signal
    def approval_decided(self, payload: dict[str, Any]) -> None:
        """Signal ``approval_decided`` from the parent conversation."""
        self.decision = payload

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("wait_approval") is True:
            try:
                await workflow.wait_condition(
                    lambda: self.decision is not None,
                    timeout=timedelta(hours=24),
                )
            except TimeoutError:
                return {
                    "status": "expired",
                    "final_text": "",
                    "usage": {},
                    "file_ids": [],
                    "child_run_id": payload.get("run_id"),
                }
            decision = self.decision or {}
            if str(decision.get("status") or "") != "approved":
                return {
                    "status": str(decision.get("status") or "rejected"),
                    "final_text": "",
                    "usage": {},
                    "file_ids": [],
                    "child_run_id": payload.get("run_id"),
                }
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        files = payload.get("file_ids") if isinstance(payload.get("file_ids"), list) else []
        return {
            "status": "completed",
            "final_text": str(payload.get("final_text") or "")[:8000],
            "usage": usage,
            "file_ids": files,
            "child_run_id": payload.get("run_id"),
        }


@workflow.defn(name="DelegationWorkflow")
class AgentRunWorkflow:
    """Start parallel children and merge their results. Closing the parent cancels them."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        remaining = payload.get("remaining_budget")
        budget = remaining if isinstance(remaining, dict) else {}
        exhausted = budget_exhausted(budget)
        if exhausted:
            return {"status": "budget_exceeded", "limit": exhausted, "children": [], "usage": {}}
        briefs = payload.get("delegations")
        items = briefs if isinstance(briefs, list) else []
        handles = []
        for index, brief in enumerate(items):
            if not isinstance(brief, dict):
                continue
            request = {
                "run_id": payload.get("run_id"),
                "depth": payload.get("depth") or 0,
                "max_depth": payload.get("max_depth") or 3,
                "remaining_budget": budget,
                "child_budget": brief.get("budget")
                if isinstance(brief.get("budget"), dict)
                else {},
                "allowed": payload.get("allowed") or [],
                "allow_self_clone": payload.get("allow_self_clone") is True,
                "agent": brief.get("agent"),
                "task": brief.get("task"),
                "index": index,
                "files": brief.get("files") or [],
                "wait_approval": brief.get("wait_approval") is True,
            }
            planned = await workflow.execute_activity(
                create_child_run,
                request,
                start_to_close_timeout=timedelta(seconds=30),
            )
            if not isinstance(planned, dict) or planned.get("error"):
                status = "failed" if not isinstance(planned, dict) else str(planned.get("error"))
                return {"status": status, "children": [], "usage": {}}
            child_payload = planned.get("child_payload")
            body = child_payload if isinstance(child_payload, dict) else {}
            handle = await workflow.start_child_workflow(
                ChildRunWorkflow.run,
                body,
                id=f"run-{planned.get('child_run_id')}",
                parent_close_policy=ParentClosePolicy.REQUEST_CANCEL,
            )
            handles.append(handle)
        results = await asyncio.gather(*handles) if handles else []
        usage = {"tokens_in": 0, "tokens_out": 0}
        children: list[dict[str, Any]] = []
        texts: list[str] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            raw_usage = result.get("usage")
            child_usage = raw_usage if isinstance(raw_usage, dict) else {}
            usage["tokens_in"] += _count(child_usage.get("tokens_in"))
            usage["tokens_out"] += _count(child_usage.get("tokens_out"))
            texts.append(str(result.get("final_text") or ""))
            children.append(
                {
                    "child_run_id": result.get("child_run_id"),
                    "status": result.get("status"),
                    "usage": child_usage,
                }
            )
        return {
            "status": "completed",
            "final_text": "\n\n".join(item for item in texts if item)[:8000],
            "children": children,
            "usage": usage,
        }


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value
