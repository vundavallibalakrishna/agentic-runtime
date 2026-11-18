"""Read a chat completion as it is written, so an answer reaches the reader word by word.

A model round is asked for as a stream when a caller is listening for text
(``listening``). The pieces are handed on at once, and when the stream ends they are put
back together into the same shape a completion asked for in one piece has, so everything
after the call (tool calls, token counts, the thinking trace) is unchanged.

Text between ``<think>`` tags is the model's private reasoning. It is kept out of what is
handed on, the way ``models.logic.strip_think`` keeps it out of a finished answer.
"""

from __future__ import annotations

import contextlib
import contextvars
import os
import time
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

import httpx
import orjson

if TYPE_CHECKING:
    from typing import Any

TextSink = Callable[[str], None]

_OPEN = "<think>"
_CLOSE = "</think>"
_SINK: contextvars.ContextVar[TextSink | None] = contextvars.ContextVar("model_text_sink")
# The documented default of AR_DELTA_COALESCE_MS (docs/07-ops/environments.md).
_DEFAULT_WINDOW_MS = 50


@contextlib.contextmanager
def listening(sink: TextSink) -> Iterator[None]:
    """While this is open, a model round started by this task hands its text to ``sink``."""
    token = _SINK.set(sink)
    try:
        yield
    finally:
        _SINK.reset(token)


def listener() -> TextSink | None:
    """Who is listening for the text of the model round being started, if anyone."""
    return _SINK.get(None)


def coalesce_window_s() -> float:
    """How long text is gathered before it is sent as one delta (``AR_DELTA_COALESCE_MS``)."""
    raw = os.environ.get("AR_DELTA_COALESCE_MS", "").strip()
    try:
        value = int(raw) if raw else _DEFAULT_WINDOW_MS
    except ValueError:
        value = _DEFAULT_WINDOW_MS
    return max(value, 0) / 1000


class VisibleText:
    """Passes text through and holds back what sits between ``<think>`` tags.

    A tag can arrive split across two pieces, so the end of a piece that could be the
    start of a tag waits for the next piece.
    """

    def __init__(self) -> None:
        self._held = ""
        self._thinking = False

    def feed(self, piece: str) -> str:
        self._held += piece
        out: list[str] = []
        while True:
            lowered = self._held.lower()
            if self._thinking:
                end = lowered.find(_CLOSE)
                if end < 0:
                    # Reasoning is dropped. Keep only what could be the start of the close tag.
                    self._held = self._held[-(len(_CLOSE) - 1) :]
                    break
                self._held = self._held[end + len(_CLOSE) :]
                self._thinking = False
                continue
            start = lowered.find(_OPEN)
            if start >= 0:
                out.append(self._held[:start])
                self._held = self._held[start + len(_OPEN) :]
                self._thinking = True
                continue
            keep = _partial_tag(lowered)
            cut = len(self._held) - keep
            out.append(self._held[:cut])
            self._held = self._held[cut:]
            break
        return "".join(out)

    def close(self) -> str:
        """What was still waiting when the stream ended: text, unless it was reasoning."""
        rest, self._held = self._held, ""
        return "" if self._thinking else rest


def _partial_tag(lowered: str) -> int:
    """How many characters at the end could be the beginning of an opening tag."""
    for size in range(min(len(_OPEN) - 1, len(lowered)), 0, -1):
        if _OPEN.startswith(lowered[-size:]):
            return size
    return 0


class Coalescer:
    """Gathers text for a short window and sends it on as one piece.

    A model writes a few characters at a time. One stream event for each would be hundreds
    of events for an answer, so pieces that arrive inside the window travel together.
    """

    def __init__(self, send: TextSink, window_s: float | None = None) -> None:
        self._send = send
        self._window = coalesce_window_s() if window_s is None else window_s
        self._waiting: list[str] = []
        # No piece has been sent yet, so the first one goes at once whatever the clock reads.
        self._last = float("-inf")
        self.sent = False

    def feed(self, piece: str) -> None:
        if not piece:
            return
        self._waiting.append(piece)
        now = time.monotonic()
        if now - self._last >= self._window:
            self.flush()
            self._last = now

    def flush(self) -> None:
        if not self._waiting:
            return
        text, self._waiting = "".join(self._waiting), []
        self.sent = True
        self._send(text)


class _Gathered:
    """The completion being put back together from the chunks of a stream."""

    def __init__(self, sink: TextSink) -> None:
        self._sink = sink
        self._visible = VisibleText()
        self.content: list[str] = []
        self.reasoning: list[str] = []
        self.calls: dict[int, dict[str, Any]] = {}
        self.usage: dict[str, Any] | None = None
        self.model: str | None = None
        self.finish: str | None = None

    def take(self, chunk: dict[str, Any]) -> None:
        if isinstance(chunk.get("usage"), dict):
            self.usage = chunk["usage"]
        if isinstance(chunk.get("model"), str):
            self.model = chunk["model"]
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return
        self.finish = choices[0].get("finish_reason") or self.finish
        delta = choices[0].get("delta")
        if not isinstance(delta, dict):
            return
        piece = delta.get("content")
        if isinstance(piece, str) and piece:
            self.content.append(piece)
            shown = self._visible.feed(piece)
            if shown:
                self._sink(shown)
        thought = delta.get("reasoning_content")
        if isinstance(thought, str) and thought:
            self.reasoning.append(thought)
        _gather_calls(self.calls, delta.get("tool_calls"))

    def payload(self) -> dict[str, Any]:
        rest = self._visible.close()
        if rest:
            self._sink(rest)
        message: dict[str, Any] = {"role": "assistant", "content": "".join(self.content)}
        if self.reasoning:
            message["reasoning_content"] = "".join(self.reasoning)
        if self.calls:
            message["tool_calls"] = [self.calls[index] for index in sorted(self.calls)]
        whole: dict[str, Any] = {"choices": [{"message": message, "finish_reason": self.finish}]}
        if self.usage is not None:
            whole["usage"] = self.usage
        if self.model is not None:
            whole["model"] = self.model
        return whole


async def read_completion_stream(response: httpx.Response, sink: TextSink) -> dict[str, Any]:
    """Hand the answer's text to ``sink`` as it arrives and return the whole completion.

    The result has the shape of a completion asked for in one piece. If the connection
    breaks after text was handed on, what arrived is returned, so the reader keeps the part
    of the answer already shown.
    """
    gathered = _Gathered(sink)
    try:
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = orjson.loads(data)
            except ValueError:
                continue
            if isinstance(chunk, dict):
                gathered.take(chunk)
    except httpx.HTTPError:
        if not gathered.content and not gathered.calls:
            raise
    return gathered.payload()


def _gather_calls(calls: dict[int, dict[str, Any]], raw: object) -> None:
    """Add the pieces of tool calls in one chunk to the calls being put together."""
    if not isinstance(raw, list):
        return
    for item in raw:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        slot = calls.setdefault(
            index if isinstance(index, int) else len(calls),
            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if isinstance(item.get("id"), str) and item["id"]:
            slot["id"] = item["id"]
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        if isinstance(function.get("name"), str):
            slot["function"]["name"] += function["name"]
        if isinstance(function.get("arguments"), str):
            slot["function"]["arguments"] += function["arguments"]
