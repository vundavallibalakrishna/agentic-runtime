"""Markdown rendering for Slack, Teams and email."""

import re

import mistune

from ar_common.markdown_exfil import filter_markdown


def to_mrkdwn(markdown: str) -> str:
    """Slack mrkdwn. Bold and links are the forms the thread shows."""
    markdown = filter_markdown(markdown)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", markdown, flags=re.DOTALL)
    return re.sub(r"\[(.+?)\]\((.+?)\)", r"<\2|\1>", text)


def split_message(text: str, limit: int = 3500) -> list[str]:
    if len(text) <= limit:
        return [text or "…"]
    return [text[index : index + limit] for index in range(0, len(text), limit)]


def throttled_snapshots(events: list[dict[str, object]], interval_ms: int) -> list[str]:
    """Coalesce deltas so a channel is updated at most once per interval."""
    accumulated = ""
    last: int | None = None
    shots: list[str] = []
    for event in events:
        if str(event.get("type") or "") == "message.delta":
            accumulated += str(event.get("text") or "")
        stamp = int(str(event.get("ts_ms") or 0))
        if last is None or stamp - last >= interval_ms:
            shots.append(accumulated or "…")
            last = stamp
    if not shots or shots[-1] != (accumulated or "…"):
        shots.append(accumulated or "…")
    return shots


def approval_blocks(
    approval_id: str, args_hash: str, *, step_up: bool, web_url: str
) -> list[dict[str, object]]:
    if step_up:
        return [{"type": "button", "text": "Open in web", "url": web_url}]
    return [
        {
            "type": "button",
            "action_id": "approve",
            "text": "Approve",
            "value": f"{approval_id}|{args_hash}|approve",
        },
        {
            "type": "button",
            "action_id": "reject",
            "text": "Reject",
            "value": f"{approval_id}|{args_hash}|reject",
        },
    ]


def adaptive_card(
    text: str, *, approval_id: str = "", args_hash: str = "", step_up: bool = False
) -> dict[str, object]:
    body: list[dict[str, object]] = [{"type": "TextBlock", "text": text, "wrap": True}]
    actions: list[dict[str, object]] = []
    if approval_id and not step_up:
        actions = [
            {
                "type": "Action.Submit",
                "title": "Approve",
                "data": {"approval_id": approval_id, "args_hash": args_hash, "decision": "approve"},
            },
            {
                "type": "Action.Submit",
                "title": "Reject",
                "data": {"approval_id": approval_id, "args_hash": args_hash, "decision": "reject"},
            },
        ]
    elif step_up:
        actions = [
            {"type": "Action.OpenUrl", "title": "Open in web", "url": "https://localhost/approvals"}
        ]
    card: dict[str, object] = {"type": "AdaptiveCard", "version": "1.5", "body": body}
    if actions:
        card["actions"] = actions
    return card


def render_email_html(markdown: str) -> str:
    html = str(mistune.html(filter_markdown(markdown)))
    html = re.sub(r"(?is)<script.*?>.*?</script>", "", html)
    return re.sub(r"""(?is)\son\w+\s*=\s*(['"]).*?\1""", "", html)


def reply_headers(message_id: str, references: str) -> dict[str, str]:
    chain = f"{references} {message_id}".strip()
    return {"In-Reply-To": message_id, "References": chain}
