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
    from ar_common.approval_cards import slack_blocks  # noqa: PLC0415

    return slack_blocks(approval_id, args_hash, step_up=step_up, web_url=web_url)


def adaptive_card(
    text: str,
    *,
    approval_id: str = "",
    args_hash: str = "",
    step_up: bool = False,
    web_url: str = "",
    interactive: bool = False,
) -> dict[str, object]:
    from ar_common.approval_cards import teams_card  # noqa: PLC0415

    link = web_url
    if step_up and not link:
        import os  # noqa: PLC0415

        link = os.environ.get("AR_PUBLIC_URL", "http://localhost:3000").rstrip("/") + "/approvals"
    return teams_card(
        text,
        approval_id=approval_id,
        args_hash=args_hash,
        step_up=step_up,
        web_url=link,
        interactive=interactive,
    )


def render_email_html(markdown: str) -> str:
    html = str(mistune.html(filter_markdown(markdown)))
    html = re.sub(r"(?is)<script.*?>.*?</script>", "", html)
    return re.sub(r"""(?is)\son\w+\s*=\s*(['"]).*?\1""", "", html)


def reply_headers(message_id: str, references: str) -> dict[str, str]:
    chain = f"{references} {message_id}".strip()
    return {"In-Reply-To": message_id, "References": chain}
