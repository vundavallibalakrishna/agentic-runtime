"""Strict, preferred and off grounding. Spec: docs/03-specs/07-agent-runtime.md §13."""

import os
import re

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?|\n+")
_CITE = re.compile(r"\[(\d+)\]")
_HEADING = re.compile(r"^\s*#{1,6}\s")
_QUESTION = re.compile(r"\?\s*$")


def max_sentences() -> int:
    raw = os.environ.get("AR_GROUNDING_MAX_SENTENCES", "200")
    try:
        return max(1, int(raw))
    except ValueError:
        return 200


def apply_grounding(
    text: str,
    indexes: set[int],
    *,
    mode: str,
) -> tuple[str, dict[str, object] | None]:
    """Return the visible text and a report. ``off`` does not check."""
    cleaned = strip_unknown(text, indexes)
    if mode == "off":
        return cleaned, None
    claims: list[dict[str, object]] = []
    kept: list[str] = []
    factual = 0
    for sentence in _sentences(cleaned):
        if _exempt(sentence):
            kept.append(sentence)
            continue
        factual += 1
        if factual > max_sentences():
            break
        found = [int(item) for item in _CITE.findall(sentence)]
        valid = [item for item in found if item in indexes]
        if valid:
            claims.append(
                {"text": sentence.strip(), "citation_indexes": valid, "status": "grounded"}
            )
            kept.append(sentence)
            continue
        if mode == "strict":
            claims.append({"text": sentence.strip(), "citation_indexes": [], "status": "removed"})
            continue
        claims.append({"text": sentence.strip(), "citation_indexes": [], "status": "flagged"})
        kept.append(sentence)
    visible = "".join(kept).strip()
    if mode == "strict" and not visible:
        visible = (
            "This answer was removed because it was not grounded in retrieved sources, "
            "tool results or evidence."
        )
    report = {"mode": mode, "claims": claims, "sources": [], "tools": [], "approvals": []}
    return visible, report  # type: ignore[return-value]


def strip_unknown(text: str, indexes: set[int]) -> str:
    """Drop citation markers the run did not allocate."""

    def _keep(match: re.Match[str]) -> str:
        return match.group(0) if int(match.group(1)) in indexes else ""

    return _CITE.sub(_keep, text)


def cited_indexes(text: str) -> list[int]:
    return [int(item) for item in _CITE.findall(text)]


def _sentences(text: str) -> list[str]:
    return [part for part in _SENTENCE.findall(text) if part.strip()]


def _exempt(sentence: str) -> bool:
    stripped = sentence.strip()
    if not stripped:
        return True
    if _HEADING.match(stripped):
        return True
    if _QUESTION.match(stripped) and not _CITE.search(stripped):
        return True
    return bool(re.fullmatch(r"(\[\d+\]\s*)+", stripped))
