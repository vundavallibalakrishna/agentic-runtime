"""Wrap untrusted content before it enters a prompt.

Spec: docs/06-security/prompt-injection.md §3.
"""

import re
import secrets
from xml.sax.saxutils import escape

_CLOSING = (
    "</tool_result>",
    "</retrieved_documents>",
    "</document",
    "</untrusted_content>",
    "<memory",
    "</memory",
)


_ECHOED = re.compile(
    r"</?(?:untrusted_content|tool_result|retrieved_documents)\b[^>]*>\s?", re.IGNORECASE
)


def without_wrappers(answer: str) -> str:
    """A model's answer with any of the platform's own wrapper tags taken out.

    Earlier turns and tool results reach the model inside these tags. A model sometimes
    copies the tag around its own answer. The tag is the platform's marking, not part of
    what was said, so only the tag goes and the words inside stay.
    """
    if "<" not in answer:
        return answer
    return _ECHOED.sub("", answer).strip()


class WrapperFilter:
    """Takes the platform's wrapper tags out of an answer as it is written, piece by piece.

    A tag can arrive split across pieces, so text from an unclosed ``<`` waits for the
    next piece. A ``<`` that never closes is let through once it is too long to be a tag.
    """

    _LONGEST = 400

    def __init__(self) -> None:
        self._held = ""

    def feed(self, piece: str) -> str:
        text = self._held + piece
        cut = text.rfind("<")
        if cut >= 0 and ">" not in text[cut:] and len(text) - cut < self._LONGEST:
            self._held, text = text[cut:], text[:cut]
        else:
            self._held = ""
        return _ECHOED.sub("", text)

    def close(self) -> str:
        rest, self._held = self._held, ""
        return _ECHOED.sub("", rest)


def neutralise(content: str) -> str:
    """Replace wrapper-breaking tags. This runs before redaction and truncation."""
    safe = content
    for tag in _CLOSING:
        safe = safe.replace(tag, tag.replace("<", "&lt;"))
    return safe


def wrap_tool_result(*, tool: str, call_id: str, content: str, nonce: str | None = None) -> str:
    """One tool result."""
    token = nonce or secrets.token_hex(8)
    body = neutralise(content)
    return (
        f'<tool_result tool="{escape(tool)}" call_id="{escape(call_id)}" '
        f'trust="untrusted" nonce="{token}">\n{body}\n</tool_result>'
    )


def wrap_documents(documents: list[dict[str, str]], *, nonce: str | None = None) -> str:
    """Retrieved chunks. Each document carries index, collection, title and source."""
    token = nonce or secrets.token_hex(8)
    parts = [f'<retrieved_documents trust="untrusted" nonce="{token}">']
    for index, document in enumerate(documents, start=1):
        body = neutralise(document.get("text", ""))
        collection = escape(document.get("collection", ""))
        title = escape(document.get("title", ""))
        source = escape(document.get("source", ""))
        parts.append(
            f'<document index="{index}" collection="{collection}" '
            f'title="{title}" source="{source}">\n{body}\n</document>'
        )
    parts.append("</retrieved_documents>")
    return "\n".join(parts)


def wrap_untrusted(*, source: str, content: str, nonce: str | None = None) -> str:
    """Files, channel messages, email, events, subagent output and pages."""
    token = nonce or secrets.token_hex(8)
    body = neutralise(content)
    return (
        f'<untrusted_content source="{escape(source)}" trust="untrusted" nonce="{token}">\n'
        f"{body}\n</untrusted_content>"
    )
