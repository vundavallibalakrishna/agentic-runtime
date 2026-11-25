"""Interactive approval cards for Slack and Teams.

The channels service and the approval announcer both build from here, so a card
recorded in the product and a card posted to a workspace are the same card.
"""

from __future__ import annotations


def _button(label: str, action_id: str, *, url: str = "", value: str = "") -> dict[str, object]:
    button: dict[str, object] = {
        "type": "button",
        "action_id": action_id,
        "text": {"type": "plain_text", "text": label, "emoji": True},
    }
    if url:
        button["url"] = url
    if value:
        button["value"] = value
    return button


def slack_blocks(
    approval_id: str, args_hash: str, *, step_up: bool, web_url: str
) -> list[dict[str, object]]:
    """Approve, reject, and a link to the one-item review page.

    Buttons live in one actions block. Slack rejects a button whose text is a string.
    """
    if step_up:
        elements = [_button("Open in web", "review", url=web_url)]
    else:
        elements = [
            _button("Approve", "approve", value=f"{approval_id}|{args_hash}|approve"),
            _button("Reject", "reject", value=f"{approval_id}|{args_hash}|reject"),
            _button("Review", "review", url=web_url),
        ]
    return [{"type": "actions", "elements": elements}]


def teams_card(
    text: str,
    *,
    approval_id: str = "",
    args_hash: str = "",
    step_up: bool = False,
    web_url: str = "",
    interactive: bool = False,
) -> dict[str, object]:
    """An adaptive card. Submit actions exist only for a bot credential.

    An incoming webhook cannot receive Action.Submit, so that card is links only.
    """
    body: list[dict[str, object]] = [{"type": "TextBlock", "text": text, "wrap": True}]
    actions: list[dict[str, object]] = []
    link = web_url or ""
    if interactive and approval_id and not step_up:
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
    card: dict[str, object] = {"type": "AdaptiveCard", "version": "1.5", "body": body}
    if actions:
        card["actions"] = actions
    return card


def teams_incoming(card: dict[str, object]) -> dict[str, object]:
    """The envelope an incoming webhook accepts. The card is an attachment."""
    return {
        "type": "message",
        "attachments": [
            {"contentType": "application/vnd.microsoft.card.adaptive", "content": card}
        ],
    }
