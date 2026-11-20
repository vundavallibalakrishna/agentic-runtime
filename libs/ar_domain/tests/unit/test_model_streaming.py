"""An answer is read as the model writes it, and put back together unchanged."""

import asyncio
from collections.abc import AsyncIterator

import httpx
import orjson
import pytest

from ar_domain.models.logic import completion_message
from ar_domain.models.streaming import (
    Coalescer,
    VisibleText,
    listener,
    listening,
    read_completion_stream,
)


def _sse(*chunks: dict[str, object]) -> httpx.Response:
    lines = [b"data: " + orjson.dumps(chunk) + b"\n\n" for chunk in chunks]
    return httpx.Response(200, content=b"".join(lines) + b"data: [DONE]\n\n")


def _delta(**delta: object) -> dict[str, object]:
    return {"choices": [{"delta": delta}]}


def test_reasoning_between_think_tags_is_held_back_even_when_a_tag_is_split() -> None:
    text = VisibleText()
    shown = [
        text.feed("Hello <th"),
        text.feed("ink>private rea"),
        text.feed("soning</thi"),
        text.feed("nk> world"),
        text.close(),
    ]
    assert "".join(shown) == "Hello  world"
    assert shown[0] == "Hello "  # the possible start of a tag waits, the text before it does not


def test_text_that_only_looks_like_a_tag_is_let_through_at_the_end() -> None:
    text = VisibleText()
    assert text.feed("a < b and <t") == "a < b and "
    assert text.close() == "<t"


def test_a_stream_that_ends_inside_reasoning_shows_none_of_it() -> None:
    text = VisibleText()
    assert text.feed("<think>never closed") == ""
    assert text.close() == ""


def test_pieces_inside_the_window_travel_together() -> None:
    sent: list[str] = []
    gathered = Coalescer(sent.append, window_s=3600)
    gathered.feed("a")  # the first piece goes at once: nothing was sent before it
    gathered.feed("b")
    gathered.feed("c")
    assert sent == ["a"]
    gathered.flush()
    assert sent == ["a", "bc"]
    assert gathered.sent is True


def test_a_coalescer_that_was_given_nothing_sends_nothing() -> None:
    sent: list[str] = []
    gathered = Coalescer(sent.append, window_s=0)
    gathered.feed("")
    gathered.flush()
    assert sent == []
    assert gathered.sent is False


async def test_the_text_arrives_piece_by_piece_and_the_whole_reads_like_one_completion() -> None:
    heard: list[str] = []
    payload = await read_completion_stream(
        _sse(
            _delta(role="assistant", content="<think>plan</think>"),
            _delta(content="A kiln "),
            _delta(content="fires clay."),
            {"choices": [{"delta": {}, "finish_reason": "stop"}], "model": "m-1"},
            {"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 5}},
        ),
        heard.append,
    )
    assert heard == ["A kiln ", "fires clay."]
    parsed = completion_message(payload)
    assert parsed["text"] == "A kiln fires clay."
    assert parsed["reasoning"] == "plan"
    usage = parsed["usage"]
    assert isinstance(usage, dict)
    assert (usage["tokens_in"], usage["tokens_out"]) == (7, 5)
    assert payload["model"] == "m-1"


async def test_a_tool_call_sent_in_pieces_is_put_back_together() -> None:
    heard: list[str] = []
    first = {"index": 0, "id": "call_1", "function": {"name": "files.read", "arguments": '{"file'}}
    payload = await read_completion_stream(
        _sse(
            _delta(tool_calls=[first]),
            _delta(tool_calls=[{"index": 0, "function": {"arguments": '_id": "f1"}'}}]),
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        ),
        heard.append,
    )
    assert heard == []
    calls = completion_message(payload)["tool_calls"]
    assert isinstance(calls, list) and len(calls) == 1
    assert calls[0]["id"] == "call_1"
    assert calls[0]["name"] == "files.read"
    assert calls[0]["arguments"] == {"file_id": "f1"}


def test_a_listener_is_heard_only_inside_its_block() -> None:
    assert listener() is None
    heard: list[str] = []
    with listening(heard.append):
        sink = listener()
        assert sink is not None
        sink("x")
    assert listener() is None
    assert heard == ["x"]


class _Stalling:
    """A stream that sends its lines and then only keep-alives, and never ends."""

    def __init__(self, *lines: str) -> None:
        self._lines = lines

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line
        while True:
            await asyncio.sleep(0.01)
            yield ": keep-alive"


async def test_a_stream_that_never_finishes_is_given_up_on() -> None:
    with pytest.raises(httpx.ReadTimeout):
        await read_completion_stream(_Stalling(), lambda _text: None, within_s=0.05)  # type: ignore[arg-type]


async def test_text_already_shown_is_kept_when_the_stream_stalls() -> None:
    heard: list[str] = []
    line = "data: " + orjson.dumps(_delta(content="A kiln ")).decode()
    payload = await read_completion_stream(_Stalling(line), heard.append, within_s=0.05)  # type: ignore[arg-type]
    assert heard == ["A kiln "]
    assert completion_message(payload)["text"] == "A kiln"


async def test_half_a_tool_call_is_not_kept_when_the_stream_stalls() -> None:
    call = {"index": 0, "id": "c1", "function": {"name": "lookup", "arguments": '{"q": "ki'}}
    line = "data: " + orjson.dumps(_delta(content="Looking. ", tool_calls=[call])).decode()
    with pytest.raises(httpx.ReadTimeout):
        await read_completion_stream(_Stalling(line), lambda _text: None, within_s=0.05)  # type: ignore[arg-type]


def test_a_wrapper_tag_split_across_pieces_never_reaches_the_reader() -> None:
    from ar_common.wrapping import WrapperFilter

    plain = WrapperFilter()
    pieces = [
        '<untrusted_content source="assistant:turn" tru',
        'st="untrusted" nonce="ab12">\n',
        "Done. x < y.",
        "\n</untrusted",
        "_content>",
    ]
    shown = "".join(plain.feed(piece) for piece in pieces) + plain.close()
    assert shown.strip() == "Done. x < y."
    assert "untrusted" not in shown


def test_what_was_sent_is_kept_for_a_reply_that_is_stopped() -> None:
    sent: list[str] = []
    gathered = Coalescer(sent.append, window_s=0)
    gathered.feed("Bridges ")
    gathered.feed("began ")
    waiting = Coalescer(sent.append, window_s=3600)
    waiting.feed("as ")
    waiting.feed("logs")
    assert "".join(gathered.written) == "Bridges began "
    # The second piece is still waiting for its window; flushing sends and keeps it.
    assert "".join(waiting.written) == "as "
    waiting.flush()
    assert "".join(waiting.written) == "as logs"
