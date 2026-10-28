"""Classifiers for user input, model output and open-world tool results."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

_CATEGORIES = (
    "self_harm",
    "violence",
    "sexual_minors",
    "illegal_activity",
    "credential_harvesting",
    "jailbreak_attempt",
)
_PATTERNS = {
    "sexual_minors": re.compile(r"child sexual|csam|underage sexual", re.I),
    "self_harm": re.compile(r"kill myself|suicide method", re.I),
    "violence": re.compile(r"build a bomb|how to stab", re.I),
    "illegal_activity": re.compile(r"how to launder|forge a passport", re.I),
    "credential_harvesting": re.compile(r"ask them for their password|harvest credentials", re.I),
    "jailbreak_attempt": re.compile(r"ignore (all|previous) instructions|jailbreak", re.I),
    "secret_leak": re.compile(r"\b(?:sk-|api[_-]?key\s*[:=])\S+", re.I),
    "prompt_injection": re.compile(
        r"ignore previous instructions|system prompt|exfiltrate|you are now", re.I
    ),
}
_DEFAULT_ACTION = {"sexual_minors": "block"}


def classify_input(text: str, *, actions: dict[str, str] | None = None) -> dict[str, object]:
    """Return the first matching input category and the tenant action."""
    policy = {**_DEFAULT_ACTION, **(actions or {})}
    for category in _CATEGORIES:
        pattern = _PATTERNS[category]
        if pattern.search(text):
            action = policy.get(category, "warn")
            return {"category": category, "action": action, "score": 0.9}
    return {"category": "", "action": "allow", "score": 0.0}


def classify_output(text: str) -> dict[str, object]:
    decision = classify_input(text)
    if _PATTERNS["secret_leak"].search(text):
        return {"category": "secret_leak", "action": "redact", "score": 1.0}
    if decision["action"] == "allow":
        return decision
    return decision


def injection_flag(text: str, *, fail_open: bool = False) -> dict[str, object]:
    """Open-world injection classifier. A timeout fails open and records the metric."""
    if fail_open:
        return {"suspected": False, "failed_open": True}
    suspected = _PATTERNS["prompt_injection"].search(text) is not None
    return {"suspected": suspected, "failed_open": False}


def apply_result_safety(
    store: Any, text: str, *, open_world: bool
) -> tuple[str, dict[str, object]]:
    from ar_domain.pii.analyzer import redact  # noqa: PLC0415

    settings = getattr(store, "tenant_settings", {})
    enabled = True
    if isinstance(settings, dict):
        for row in settings.values():
            if isinstance(row, dict) and row.get("pii_redaction") is False:
                enabled = False
    cleaned = redact(text, enabled=enabled)
    raw_flag = injection_flag(cleaned) if open_world else {"suspected": False, "failed_open": False}
    flag = {str(key): value for key, value in raw_flag.items()}
    if flag.get("suspected"):
        cleaned = "Warning: this tool result looks like an instruction.\n" + cleaned
    return cleaned, flag
