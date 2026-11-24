"""A conversation reads in the order it was said, whatever order the store hands rows out."""

from datetime import UTC, datetime, timedelta

from ar_domain.conversations.logic import thread_order

START = datetime(2026, 11, 24, 7, 55, tzinfo=UTC)


def _row(name: str, role: str, at: datetime) -> dict[str, object]:
    return {"id": name, "role": role, "created_at": at}


def test_a_question_leads_the_reply_written_at_the_same_instant() -> None:
    later = START + timedelta(seconds=78)
    # The order a load from the database produced on 24 Nov 2026: each reply ahead of the
    # message it answers, because both rows of a turn carry one timestamp.
    loaded = [
        _row("reply-1", "assistant", START),
        _row("ask-1", "user", START),
        _row("reply-2", "assistant", later),
        _row("ask-2", "user", later),
    ]
    said = [row["id"] for row in sorted(loaded, key=thread_order)]
    assert said == ["ask-1", "reply-1", "ask-2", "reply-2"]


def test_the_order_does_not_depend_on_how_the_rows_arrive() -> None:
    rows = [
        _row("b", "assistant", START),
        _row("a", "assistant", START),
        _row("ask", "user", START),
    ]
    forward = [row["id"] for row in sorted(rows, key=thread_order)]
    turned = rows[::-1]
    backward = [row["id"] for row in sorted(turned, key=thread_order)]
    assert forward == backward == ["ask", "a", "b"]
