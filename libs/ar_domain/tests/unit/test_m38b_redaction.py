"""Redaction does not change the facts (M38b-T09, finding F12, decision OQ-97).

Every match of every recogniser was masked, whatever its score. On the live tenant a sum
reached the model as ``[US_DRIVER_LICENSE]``, the regions East and South as ``[NRP]``,
order dates as ``[DATE_TIME]``, and two rows of a CSV were fused, so the answers were
wrong. A kind is now masked only when the tenant lists it and the match is sure enough.
"""

from __future__ import annotations

import uuid

import pytest

from ar_common.errors import ValidationFailedError
from ar_contracts.tenants import PlanLimits, TenantSettings
from ar_domain.identity.limits import merge_settings, validate_tenant_settings
from ar_domain.pii import analyzer
from ar_domain.pii.analyzer import (
    DEFAULT_ENTITIES,
    DEFAULT_MIN_SCORE,
    Masking,
    maskable_entities,
    redact,
)
from ar_domain.pii.settings import masking_from, masking_view
from ar_domain.security.guardrails import apply_result_safety
from ar_testing.demo import demo_store

# What the live run corrupted. Each must reach the model exactly as written.
FACTS = [
    "829348951",
    "region\nEast     1042.5\nNorth     817.0\nSouth     420.5\nWest      522.5\n",
    (
        "order_id,region,product,units,unit_price,order_date\n"
        "1004,East,Widget,30,18.75,2026-08-21\n"
        "1005,South,Widget,9,19.50,2026-09-02\n"
    ),
    '  File "_agent.py", line 3, in <module>',
    "S3-compatible storage: Read an object's text.",
    "worktrees/m38b-t03/.venv/lib/python3.14/site-packages/pandas",
    "Each full-time employee accrues 1.75 days of paid leave per month of service.",
    "order 9876543210 shipped from Lyon to Ada Lovelace on Friday",
    "The server is at 10.0.0.5 and the page is https://example.com/a",
]


@pytest.mark.parametrize("fact", FACTS)
def test_an_ordinary_result_reaches_the_model_unchanged(fact: str) -> None:
    assert redact(fact) == fact


def test_what_identifies_a_person_by_its_format_is_masked_without_context() -> None:
    text = "Write to ada@acme.com. Card 4111 1111 1111 1111. IBAN GB82 WEST 1234 5698 7654 32."
    masked = redact(text)
    assert masked == "Write to [EMAIL_ADDRESS]. Card [CREDIT_CARD]. IBAN [IBAN_CODE]."


def test_a_card_number_that_fails_its_checksum_is_left() -> None:
    assert redact("Card 4111 1111 1111 1112") == "Card 4111 1111 1111 1112"


def test_the_default_list_is_email_phone_card_and_iban() -> None:
    assert set(DEFAULT_ENTITIES) == {
        "credit_card",
        "email_address",
        "iban_code",
        "phone_number",
    }


@pytest.mark.parametrize(
    ("bare", "named", "token"),
    [
        ("+44 20 7946 0958", "Phone: +44 20 7946 0958", "[PHONE_NUMBER]"),
    ],
)
def test_a_number_is_masked_only_when_a_word_nearby_says_what_it_is(
    bare: str, named: str, token: str
) -> None:
    assert redact(bare) == bare
    assert token in redact(named)


def test_a_locale_kind_is_not_masked_until_the_tenant_lists_it() -> None:
    number = "234123412346"
    assert redact(f"Aadhaar {number}") == f"Aadhaar {number}"
    opted = Masking(entities=frozenset({*DEFAULT_ENTITIES, "us_ssn"}))
    assert "[US_SSN]" in redact("My SSN is 536-90-4399", masking=opted)


def test_matches_that_overlap_become_one_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tokens used to be written one inside the other: ``[US_DRIVER_LICENSE]ORT]UMBER]E]``."""
    text = "id 123456789 end"

    def spans(_text: str, _entities: frozenset[str]) -> list[dict[str, object]]:
        return [
            {"entity": "us_passport", "start": 3, "end": 12, "score": 0.7},
            {"entity": "us_ssn", "start": 3, "end": 12, "score": 0.9},
            {"entity": "us_bank_number", "start": 5, "end": 12, "score": 0.65},
        ]

    monkeypatch.setattr(analyzer, "_presidio", spans)
    masking = Masking(entities=frozenset({"us_passport", "us_ssn", "us_bank_number"}))
    assert redact(text, masking=masking) == "id [US_SSN] end"


def test_a_tenant_chooses_the_kinds_and_how_sure_a_match_must_be() -> None:
    text = "Ada Lovelace, +44 20 7946 0958, ada@acme.com"
    assert redact(text) == "Ada Lovelace, +44 20 7946 0958, [EMAIL_ADDRESS]"
    names_too = Masking(entities=frozenset({*DEFAULT_ENTITIES, "person"}))
    assert redact(text, masking=names_too).startswith("[PERSON], ")
    lower_bar = Masking(min_score=0.4)
    assert "[PHONE_NUMBER]" in redact(text, masking=lower_bar)
    assert redact(text, masking=Masking(entities=frozenset())) == text


def test_tenant_settings_become_the_masking() -> None:
    assert masking_from({}) == Masking()
    assert masking_from({}).min_score == DEFAULT_MIN_SCORE
    chosen = masking_from(
        {
            "redaction_entities": ["EMAIL_ADDRESS", "person"],
            "redaction_min_score": 0.8,
            "redaction_skip_entities": ["Person"],
        }
    )
    assert chosen == Masking(entities=frozenset({"email_address"}), min_score=0.8)
    assert masking_from({"redaction_entities": []}).entities == frozenset()


def test_a_tool_result_follows_the_calling_tenants_choice() -> None:
    store = demo_store()
    names, default = uuid.uuid4(), uuid.uuid4()
    store.tenant_settings[names] = {"privacy": {"redaction_entities": ["person"]}}
    text = "Ada Lovelace wrote from ada@acme.com"
    chose, _ = apply_result_safety(store, text, open_world=False, tenant_id=names)
    other, _ = apply_result_safety(store, text, open_world=False, tenant_id=default)
    assert chose == "[PERSON] wrote from ada@acme.com"
    assert other == "Ada Lovelace wrote from [EMAIL_ADDRESS]"


def test_an_unknown_kind_is_refused_by_name_and_null_returns_to_the_default() -> None:
    limits = PlanLimits()
    current = TenantSettings()
    chosen = merge_settings(current, {"privacy": {"redactionEntities": ["person", "us_ssn"]}})
    assert validate_tenant_settings(chosen, limits).privacy.redaction_entities == [
        "person",
        "us_ssn",
    ]
    back = merge_settings(chosen, {"privacy": {"redactionEntities": None}})
    assert back.privacy.redaction_entities is None
    wrong = merge_settings(current, {"privacy": {"redactionEntities": ["shoe_size"]}})
    with pytest.raises(ValidationFailedError, match="shoe_size"):
        validate_tenant_settings(wrong, limits)
    with pytest.raises(ValidationFailedError):
        merge_settings(current, {"privacy": {"redactionMinScore": 1.5}})


def test_the_view_lists_every_kind_and_what_the_tenant_does_with_it() -> None:
    view = masking_view({})
    kinds = {row["name"]: row for row in view["kinds"]}
    assert view["enabled"] is True
    assert view["uses_default"] is True
    assert view["min_score"] == view["default_min_score"] == DEFAULT_MIN_SCORE
    assert set(kinds) == set(maskable_entities())
    assert kinds["email_address"] == {
        "name": "email_address",
        "source": "format",
        "masked": True,
        "default": True,
    }
    assert kinds["person"]["source"] == "language"
    assert kinds["person"]["masked"] is False
    chosen = masking_view(
        {
            "features": {"pii_redaction": False},
            "privacy": {"redaction_entities": ["person"], "redaction_min_score": 0.9},
        }
    )
    picked = {row["name"] for row in chosen["kinds"] if row["masked"]}
    assert (chosen["enabled"], chosen["uses_default"], chosen["min_score"]) == (False, False, 0.9)
    assert picked == {"person"}


def test_the_language_model_is_never_downloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model that is not installed is an error to fix, not something to fetch."""
    monkeypatch.setenv("AR_PII_LANGUAGE_MODEL", "en_core_web_absent")
    with pytest.raises(RuntimeError, match="en_core_web_absent"):
        analyzer._language_model()
    monkeypatch.delenv("AR_PII_LANGUAGE_MODEL")
    assert analyzer._language_model() == "en_core_web_sm"
