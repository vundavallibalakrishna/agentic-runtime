"""Slack and Teams approval cards have the shape those APIs accept.

Label: unit
"""

from ar_common.approval_cards import slack_blocks, teams_card, teams_incoming


def test_slack_buttons_are_an_actions_block() -> None:
    blocks = slack_blocks("approval-1", "hash", step_up=False, web_url="https://example/review")
    assert blocks[0]["type"] == "actions"
    elements = blocks[0]["elements"]
    assert isinstance(elements, list)
    assert [item["action_id"] for item in elements] == ["approve", "reject", "review"]
    assert elements[0]["text"] == {"type": "plain_text", "text": "Approve", "emoji": True}
    assert elements[2]["url"] == "https://example/review"


def test_a_webhook_card_is_links_and_a_bot_card_can_submit() -> None:
    link = teams_card("Please review", web_url="https://example/review")
    assert link["actions"] == [
        {"type": "Action.OpenUrl", "title": "Review", "url": "https://example/review"}
    ]
    posted = teams_incoming(link)
    assert posted["type"] == "message"
    attachment = posted["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert attachment["content"]["type"] == "AdaptiveCard"
    interactive = teams_card(
        "Please review",
        approval_id="a1",
        args_hash="h",
        web_url="https://example/review",
        interactive=True,
    )
    kinds = [action["type"] for action in interactive["actions"]]
    assert kinds == ["Action.Submit", "Action.Submit", "Action.OpenUrl"]
