"""Delivery tools. W2, never offered to models, entitled only for routine runs.

Spec: docs/03-specs/15-routines-triggers.md §4.
"""

TOOLS = (
    "delivery.slack_post",
    "delivery.teams_post",
    "delivery.email_send",
    "delivery.webhook_post",
)


def offered_to_model() -> bool:
    """The model never sees these tools. The runtime builds the calls."""
    return False
