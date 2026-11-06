"""Classifiers for user input, model output and open-world tool results."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.pii.analyzer import Masking

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
    store: Any,
    text: str,
    *,
    open_world: bool,
    analysis: bool = False,
    tenant_id: uuid.UUID | None = None,
    agent_version_id: uuid.UUID | None = None,
) -> tuple[str, dict[str, object]]:
    """Mask tool text that leaves the trust boundary.

    Document analysis (check, compare, read, and the other library tools except
    ``redact``) keeps dates, locations and control ids unless the tenant sets
    ``features.documentAnalysisRedaction`` or the agent sets ``safety.piiMasking``.
    Other tool results still follow ``features.piiRedaction`` (default on).
    """
    from ar_domain.pii.analyzer import Masking, redact  # noqa: PLC0415

    masking = masking_for(store, tenant_id)
    if analysis and not analysis_redaction_enabled(store, tenant_id, agent_version_id):
        cleaned = redact(text, enabled=True, profile="analysis", masking=masking)
    elif analysis:
        # The tenant or the agent asked for document analysis to be masked in full.
        cleaned = redact(text, enabled=True, profile="outbound", masking=Masking.thorough())
    elif pii_redaction_enabled(store, tenant_id):
        cleaned = redact(text, enabled=True, profile="outbound", masking=masking)
    else:
        cleaned = text
    raw_flag = injection_flag(cleaned) if open_world else {"suspected": False, "failed_open": False}
    flag = {str(key): value for key, value in raw_flag.items()}
    if flag.get("suspected"):
        cleaned = "Warning: this tool result looks like an instruction.\n" + cleaned
    return cleaned, flag


def analysis_redaction_enabled(
    store: Any, tenant_id: uuid.UUID | None, agent_version_id: uuid.UUID | None = None
) -> bool:
    """True when document analysis should run the full Presidio mask.

    The default is false so a policy check sees the library text.
    """
    settings = _settings_for(store, tenant_id)
    if _flag(settings, "document_analysis_redaction", default=False):
        return True
    return _agent_pii_masking(store, agent_version_id)


def pii_redaction_enabled(store: Any, tenant_id: uuid.UUID | None) -> bool:
    """Tenant feature ``pii_redaction``. Missing settings stay on."""
    return _flag(_settings_for(store, tenant_id), "pii_redaction", default=True)


def masking_for(store: Any, tenant_id: uuid.UUID | None) -> Masking:
    """What this tenant masks in a tool result (``privacy`` in its settings, OQ-97)."""
    from ar_domain.identity.tenant_settings import section  # noqa: PLC0415
    from ar_domain.pii.settings import masking_from  # noqa: PLC0415

    return masking_from(section(_settings_for(store, tenant_id), "privacy"))


def _settings_for(store: Any, tenant_id: uuid.UUID | None) -> dict[str, object]:
    """The calling tenant's row only. No tenant means the defaults, never another tenant."""
    from ar_domain.identity.tenant_settings import settings_for  # noqa: PLC0415

    return settings_for(store, tenant_id)


def _flag(settings: dict[str, object], name: str, *, default: bool) -> bool:
    features = settings.get("features")
    if isinstance(features, dict) and name in features:
        return bool(features[name])
    if name in settings:
        return bool(settings[name])
    return default


def _agent_pii_masking(store: Any, agent_version_id: uuid.UUID | None) -> bool:
    if not isinstance(agent_version_id, uuid.UUID):
        return False
    versions = getattr(store, "versions", None)
    if not isinstance(versions, dict):
        return False
    row = versions.get(agent_version_id)
    if not isinstance(row, dict):
        return False
    definition = row.get("definition")
    if not isinstance(definition, dict):
        return False
    safety = definition.get("safety")
    if not isinstance(safety, dict):
        return False
    return safety.get("pii_masking") is True
