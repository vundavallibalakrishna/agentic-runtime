"""Hint at a skill when its description matches the task.

The match is a visible decision: the run records the skill and the words that
overlapped. It no longer loads the skill's body — the model reads the hint and the
skill list and calls ``skills.load`` when it wants the instructions (M39-T05).
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from ar_domain.skills.book import SkillBook
from ar_domain.skills.logic import split_skill_ref

if TYPE_CHECKING:
    from typing import Any

_TOKEN = re.compile(r"[a-z0-9]{4,}")
_STOP = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "your",
        "when",
        "user",
        "asks",
        "about",
        "into",
        "they",
        "them",
        "have",
        "will",
        "should",
        "using",
        "used",
        "only",
        "than",
        "then",
        "what",
        "which",
        "where",
        "please",
        "write",
        "make",
    }
)


def match_skill(
    store: Any, run: dict[str, object], definition: dict[str, object], task: str
) -> dict[str, object] | None:
    """Return a hint at the most relevant attached skill, or None. It does not load it."""
    tenant = run.get("tenant_id")
    if not isinstance(tenant, uuid.UUID):
        return None
    best: tuple[float, list[str], dict[str, object]] | None = None
    book = SkillBook(store)
    for raw in _strings(definition.get("skills")):
        slug, _constraint = split_skill_ref(raw)
        skill = book.published_by_slug(tenant, slug)
        if skill is None:
            continue
        score, terms = _overlap(
            str(skill.get("description") or ""), str(skill.get("name") or ""), task
        )
        if score < 0.34 or len(terms) < 2:
            continue
        if best is None or score > best[0]:
            best = (score, terms, skill)
    if best is None:
        return None
    _score, terms, skill = best
    slug = str(skill.get("slug") or "")
    reason = "description matched: " + ", ".join(terms[:8])
    return {
        "slug": slug,
        "name": str(skill.get("name") or slug),
        "reason": reason,
        "version": skill.get("published_version"),
    }


def _overlap(description: str, name: str, task: str) -> tuple[float, list[str]]:
    described = _tokens(f"{name} {description}")
    asked = _tokens(task)
    if not described or not asked:
        return 0.0, []
    shared = sorted(described & asked)
    return len(shared) / len(described), shared


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN.findall(text.lower()) if token not in _STOP}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
