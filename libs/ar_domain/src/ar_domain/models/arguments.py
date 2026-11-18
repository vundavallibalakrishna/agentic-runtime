"""Tool-call arguments from an OpenAI-compatible model.

Open-weight models often wrap JSON in a fence, trail it with prose, leave a
trailing comma, or emit a Python dict. A string that still does not parse is
an error. It is never replaced with an empty object, because an empty object
is a real call for a tool that takes no arguments.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

import orjson

_MAX_CHARS = 100_000


@dataclass(frozen=True, slots=True)
class ParsedArguments:
    """A JSON object, or the reason the text could not become one."""

    ok: bool
    arguments: dict[str, object]
    error: str
    repaired: bool
    raw: str


def parse_tool_arguments(raw: object) -> ParsedArguments:
    """Parse tool arguments. Failure leaves ``arguments`` empty and ``ok`` false."""
    if isinstance(raw, dict):
        return ParsedArguments(True, dict(raw), "", False, _dump(raw))
    rejected = _reject(raw)
    if rejected is not None:
        return rejected
    text = str(raw).strip()
    parsed, repaired, kept = _parse(text)
    if parsed is None:
        return ParsedArguments(False, {}, "tool arguments were not valid JSON", repaired, str(raw))
    return ParsedArguments(True, parsed, "", repaired, kept)


def _reject(raw: object) -> ParsedArguments | None:
    if raw is None:
        return ParsedArguments(False, {}, "tool arguments were missing", False, "")
    if not isinstance(raw, str):
        return ParsedArguments(False, {}, "tool arguments were not a JSON object", False, "")
    if not raw.strip():
        return ParsedArguments(False, {}, "tool arguments were empty", False, raw)
    if len(raw.strip()) > _MAX_CHARS:
        return ParsedArguments(False, {}, "tool arguments were too long to parse", False, raw)
    return None


def _parse(text: str) -> tuple[dict[str, object] | None, bool, str]:
    """Return a dict, whether a repair was applied, and the text that parsed."""
    found = _object(text)
    if isinstance(found, dict):
        return found, False, text
    if found == "not_object":
        inner = _nested_string(text)
        if inner is None:
            return None, False, text
        return inner, True, _dump(inner)
    return _repair(text)


def _repair(text: str) -> tuple[dict[str, object] | None, bool, str]:
    candidate = text
    repaired = False
    for step in (_strip_fence, _unwrap, _strip_trailing_commas):
        nxt = step(candidate)
        if not nxt or nxt == candidate:
            continue
        candidate = nxt
        repaired = True
        found = _object(candidate)
        if isinstance(found, dict):
            return found, True, candidate
    literal = _python_object(candidate)
    if literal is not None:
        return literal, True, _dump(literal)
    return None, repaired, text


def _unwrap(text: str) -> str:
    return _extract_object(text) or text


def _object(text: str) -> dict[str, object] | str | None:
    """A dict, ``not_object`` when JSON parsed to something else, or None."""
    try:
        parsed = orjson.loads(text)
    except orjson.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return "not_object"


def _nested_string(text: str) -> dict[str, object] | None:
    """A JSON string whose contents are themselves a JSON object."""
    try:
        parsed = orjson.loads(text)
    except orjson.JSONDecodeError:
        return None
    if not isinstance(parsed, str):
        return None
    inner = _object(parsed.strip())
    return inner if isinstance(inner, dict) else None


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_object(text: str) -> str:
    """The first balanced ``{...}`` when the model wrote prose around it."""
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _strip_trailing_commas(text: str) -> str:
    """Drop commas that sit immediately before ``}`` or ``]`` outside strings."""
    out: list[str] = []
    in_string = False
    escape = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            out.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == ",":
            look = index + 1
            while look < len(text) and text[look] in " \t\r\n":
                look += 1
            if look < len(text) and text[look] in "}]":
                index += 1
                continue
        out.append(char)
        index += 1
    return "".join(out)


def _python_object(text: str) -> dict[str, object] | None:
    """A Python literal dict (single quotes, True, None). Code is not evaluated."""
    try:
        value = ast.literal_eval(text)
    except ValueError, SyntaxError, MemoryError, RecursionError:
        return None
    if not isinstance(value, dict):
        return None
    try:
        encoded = orjson.dumps(value)
        loaded = orjson.loads(encoded)
    except TypeError, orjson.JSONEncodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _dump(value: dict[str, object]) -> str:
    return orjson.dumps(value).decode()
