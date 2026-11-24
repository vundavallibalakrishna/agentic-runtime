"""Interactive approval cards for Slack and Teams.

The channels service and the approval announcer both build from here, so a card
recorded in the product and a card posted to a workspace are the same card.
"""

from __future__ import annotations


def slack_blocks(
    approval_id: str, args_hash: str, *, step_up: bool, web_url: str
) -> list[dict[str, object]]:
    """Approve, reject, and a link to the one-item review page."""
    if step_up:
        return [{"type": "button", "text": "Open in web", "url": web_url, "action_id": "review"}]
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
        {"type": "button", "action_id": "review", "text": "Review", "url": web_url},
    ]


def teams_card(
    text: str,
    *,
    approval_id: str = "",
    args_hash: str = "",
    step_up: bool = False,
    web_url: str = "",
) -> dict[str, object]:
    """An adaptive card. Step-up and review both open the review page."""
    body: list[dict[str, object]] = [{"type": "TextBlock", "text": text, "wrap": True}]
    actions: list[dict[str, object]] = []
    link = web_url or ""
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
        if link:
            actions.append({"type": "Action.OpenUrl", "title": "Review", "url": link})
    elif link:
        actions = [{"type": "Action.OpenUrl", "title": "Open in web", "url": link}]
    card: dict[str, object] = {"type": "AdaptiveCard", "version": "1.5", "body": body}
    if actions:
        card["actions"] = actions
    return card
