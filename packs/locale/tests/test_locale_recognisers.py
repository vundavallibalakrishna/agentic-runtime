"""Locale finders stay off until a tenant lists them. Label: unit."""

from ar_domain.pii.analyzer import DEFAULT_ENTITIES, Masking, redact
from locale_pack import activate


def test_default_redaction_ignores_the_locale_kinds() -> None:
    activate()
    number = "2341 2341 2346"
    assert redact(f"id {number}") == f"id {number}"
    masking = Masking(entities=frozenset({*DEFAULT_ENTITIES, "aadhaar", "pan"}))
    assert "[AADHAAR]" in redact(f"id {number}", masking=masking)
    assert "[PAN]" in redact("PAN ABCDE1234F", masking=masking)
