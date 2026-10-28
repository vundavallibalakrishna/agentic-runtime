"""Notification fan-out. Spec: docs/03-specs/20-notifications-events.md §2."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any  # noqa: TC003 — Temporal inspects annotations at runtime

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from ar_domain.channels.book import ChannelBook
    from ar_system.routines_store import current_store


@dataclass(frozen=True, slots=True)
class Notice:
    kind: str
    title: str
    body: str
    email: str | None


def _object_map(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def notices_for(topic: str, payload: dict[str, object]) -> list[Notice]:
    """Map a domain event onto in-app and email notices."""
    if topic == "invitation.created":
        email = str(payload.get("email", ""))
        return [Notice("system", "You are invited", f"Invitation for {email}", email or None)]
    if topic == "eval.completed":
        summary = payload.get("summary")
        regressions = summary.get("regressions") if isinstance(summary, dict) else []
        title = "Evaluation regressed" if regressions else "Evaluation finished"
        return [Notice("eval_completed", title, title, None)]
    if topic == "feedback.created":
        return []
    if topic == "approval.requested":
        name = str(payload.get("qualified_name") or "a tool")
        return [
            Notice(
                "approval_requested",
                "Approval requested",
                f"A run is waiting on {name}",
                "approvals@dev.local",
            )
        ]
    return []


@activity.defn(name="resolve_notification_recipients")
async def resolve_activity(payload: dict[str, Any]) -> list[dict[str, str]]:
    topic = str(payload.get("topic") or "")
    nested = payload.get("payload")
    body = _object_map(nested if isinstance(nested, dict) else payload)
    return [
        {
            "kind": notice.kind,
            "title": notice.title,
            "body": notice.body,
            "email": notice.email or "",
        }
        for notice in notices_for(topic, body)
    ]


@activity.defn(name="deliver_channel_notifications")
async def deliver_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Slack or Teams DM, then email when no identity is linked."""
    try:
        store = current_store()
    except RuntimeError:
        return {"delivered": ["email"]}
    user_id = str(payload.get("user_id") or "")
    title = str(payload.get("title") or "Notice")
    text = str(payload.get("body_markdown") or payload.get("body") or "")
    if not user_id:
        return {"delivered": ["email"]}
    return ChannelBook(store).notify(
        {"user_id": user_id, "title": title, "body_markdown": text or title}
    )


@workflow.defn(name="NotificationFanoutWorkflow")
class NotificationFanoutWorkflow:
    """Resolve recipients and deliver through the channel catalogue."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        notices = await workflow.execute_activity(
            resolve_activity,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
        )
        notice = notices[0] if isinstance(notices, list) and notices else {}
        merged = dict(payload)
        if isinstance(notice, dict):
            merged.setdefault("title", notice.get("title"))
            merged.setdefault("body_markdown", notice.get("body"))
        return await workflow.execute_activity(
            deliver_activity,
            merged,
            start_to_close_timeout=timedelta(seconds=30),
        )
