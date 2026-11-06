"""Document analysis keeps evidence, and a paraphrase is judged by the model."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from ar_common.errors import ValidationFailedError
from ar_contracts.tenants import TenantSettings
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.documents.grounding import check, prepare_analysis_text
from ar_domain.documents.library import DocumentLibrary
from ar_domain.identity.limits import merge_settings
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.pii.analyzer import Masking, redact
from ar_domain.security.guardrails import apply_result_safety
from ar_domain.tools.documents import dispatch_documents
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store

PASSAGE = (
    "The annual picnic is on Friday in the courtyard. "
    "Every employee completes a second login challenge before opening the production console. "
    "Records stay in Ireland for 90 days under control P6.3."
)
MFA = "The organization requires multi-factor authentication for access to production systems."
MARS = "The organization operates a permanent colony on Mars."
QUOTE = "Every employee completes a second login challenge before opening the production console."
EVIDENCE = "Records stay in Ireland for 90 days under control P6.3. Mail ada@example.com."


def _fake_presidio(text: str, entities: frozenset[str]) -> list[dict[str, object]]:
    """What the recogniser reports for the fixture, each match with how sure it is."""
    found: list[dict[str, object]] = []
    for kind, token, score in (
        ("date_time", "90 days", 0.85),
        ("location", "Ireland", 0.85),
        ("us_driver_license", "P6", 0.65),
        ("email_address", "ada@example.com", 1.0),
        ("location", "Cayman", 0.85),
    ):
        start = text.find(token)
        if start >= 0 and kind in entities:
            found.append(
                {"entity": kind, "start": start, "end": start + len(token), "score": score}
            )
    return found


def _document() -> dict[str, object]:
    return {
        "id": "policy",
        "title": "Access",
        "passages": [
            {
                "anchor": "p1-s0",
                "page": 1,
                "heading": "Access",
                "level": 1,
                "text": PASSAGE,
            }
        ],
    }


def _ask(task: str, evidence: str) -> str:
    del task
    if "colony on Mars" in evidence:
        return (
            '{"verdict":"not_found","anchor":"","quote":"","confidence":0,'
            '"reason":"No passage supports a Mars colony."}'
        )
    return (
        '{"verdict":"met","anchor":"p1-s0","quote":"' + QUOTE + '",'
        '"confidence":0.91,"reason":"A second login challenge is required."}'
    )


def test_analysis_profile_keeps_dates_places_and_control_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ar_domain.pii.analyzer._presidio", _fake_presidio)
    kept = redact(EVIDENCE, profile="analysis")
    assert "90 days" in kept
    assert "Ireland" in kept
    assert "P6.3" in kept
    assert "ada@example.com" not in kept
    # A tool result masks what the tenant lists. By default that is not a date or a place.
    default = redact(EVIDENCE, profile="outbound")
    assert "Records stay in Ireland for 90 days" in default
    assert "ada@example.com" not in default
    # A tenant that lists every kind gets every kind.
    outbound = redact(EVIDENCE, profile="outbound", masking=Masking.thorough())
    assert "[DATE_TIME]" in outbound
    assert "[LOCATION]" in outbound
    assert "P6.3" not in outbound
    assert "[US_DRIVER_LICENSE]" in outbound


def test_check_input_keeps_evidence_and_cites_the_paraphrase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ar_domain.pii.analyzer._presidio", _fake_presidio)
    seen: list[str] = []

    def ask(task: str, evidence: str) -> str:
        seen.append(evidence)
        return _ask(task, evidence)

    offline = check(_document(), [MFA, MARS], None)
    offline_rows = offline["rows"]
    assert isinstance(offline_rows, list)
    assert offline_rows[0]["verdict"] == "not_found"  # type: ignore[index]
    assert offline_rows[1]["verdict"] == "not_found"  # type: ignore[index]

    report = check(_document(), [MFA, MARS], ask)
    assert seen
    assert "90 days" in seen[0]
    assert "Ireland" in seen[0]
    assert "P6.3" in seen[0]
    assert "[DATE_TIME]" not in seen[0]
    assert "[LOCATION]" not in seen[0]
    assert "[US_DRIVER_LICENSE]" not in seen[0]
    rows = report["rows"]
    assert isinstance(rows, list)
    met = rows[0]
    missing = rows[1]
    assert isinstance(met, dict)
    assert isinstance(missing, dict)
    assert met["verdict"] == "met"
    citation = met["citation"]
    assert isinstance(citation, dict)
    quote = str(citation["quote"])
    assert "login challenge" in quote
    assert "picnic" not in quote.lower()
    assert quote in PASSAGE
    assert missing["verdict"] == "not_found"
    assert missing["citation"] is None


def test_near_miss_quote_cites_the_supporting_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ar_domain.pii.analyzer._presidio", _fake_presidio)

    def ask(task: str, evidence: str) -> str:
        del task, evidence
        return (
            '{"verdict":"met","anchor":"p1-s0",'
            '"quote":"second login challenge before opening production",'
            '"confidence":0.8,"reason":"The control is implemented."}'
        )

    report = check(_document(), [MFA], ask)
    row = report["rows"][0]  # type: ignore[index]
    assert isinstance(row, dict)
    quote = str(row["citation"]["quote"])  # type: ignore[index]
    assert "login challenge" in quote
    assert "picnic" not in quote.lower()
    assert quote in PASSAGE


def test_aggressive_setting_masks_the_model_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ar_domain.pii.analyzer._presidio", _fake_presidio)
    seen: list[str] = []

    def ask(task: str, evidence: str) -> str:
        del task
        seen.append(evidence)
        return '{"verdict":"not_found","quote":"","reason":"masked","confidence":0}'

    check(_document(), [MFA], ask, aggressive=True)
    assert seen
    assert "Ireland" not in seen[0]
    assert "[LOCATION]" in seen[0]
    assert "90 days" not in seen[0]


def test_tool_result_keeps_evidence_unless_the_setting_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ar_domain.pii.analyzer._presidio", _fake_presidio)
    store = demo_store()
    tenant = demo_id("tenant")
    actor = Actor(tenant, demo_id("admin"), PERMISSION_KEYS)
    policy = (
        b"# Access\n\n"
        b"The annual picnic is on Friday in the courtyard. "
        b"Every employee completes a second login challenge before opening the "
        b"production console. Records stay in Ireland for 90 days under control P6.3.\n"
    )
    saved = DocumentLibrary(store).ingest(actor, data=policy, filename="acme.md")
    other = DocumentLibrary(store).ingest(
        actor,
        data=b"# Transfers\n\nPersonal data is stored in the Cayman Islands.\n",
        filename="cayman.md",
    )
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "documents.read"
    )
    result = ToolPipeline(store).execute(
        {
            "tenant_id": tenant,
            "user_id": demo_id("admin"),
            "synthetic": True,
            "tool_version_id": version["id"],
            "arguments": {"documentId": saved["id"]},
            "model_call_id": "m32-read",
        }
    )
    preview = str(result["result_preview"])
    assert result["status"] == "succeeded"
    assert "90 days" in preview
    assert "Ireland" in preview
    assert "P6.3" in preview
    assert "[DATE_TIME]" not in preview
    assert "[US_DRIVER_LICENSE]" not in preview

    ireland = DocumentLibrary(store).ingest(
        actor,
        data=b"# Transfers\n\nPersonal data is stored in Ireland.\n",
        filename="ireland.md",
    )
    compared = dispatch_documents(
        store,
        "compare",
        {
            "_tenant_id": tenant,
            "_user_id": demo_id("admin"),
            "documentId": ireland["id"],
            "otherDocumentId": other["id"],
        },
    )
    cleaned, _flag = apply_result_safety(
        store, str(compared["text"]), open_world=True, analysis=True, tenant_id=tenant
    )
    assert "Ireland" in cleaned
    assert "Cayman" in cleaned
    assert cleaned.count("[LOCATION]") == 0

    store.tenant_settings[tenant] = {"features": {"document_analysis_redaction": True}}
    masked, _flag = apply_result_safety(
        store, str(compared["text"]), open_world=True, analysis=True, tenant_id=tenant
    )
    assert "Ireland" not in masked
    assert "[LOCATION]" in masked
    chat, _flag = apply_result_safety(
        store,
        EVIDENCE,
        open_world=False,
        analysis=False,
        tenant_id=tenant,
    )
    # Outside document analysis the tenant's list applies: an address is masked, a
    # retention period is not.
    assert "90 days" in chat
    assert "ada@example.com" not in chat


def test_root_redaction_flag_is_accepted_and_unknown_keys_are_422() -> None:
    current = TenantSettings()
    assert current.features.document_analysis_redaction is False
    folded = merge_settings(current, {"piiRedaction": False})
    assert folded.features.pii_redaction is False
    opted = merge_settings(
        current, {"features": {"documentAnalysisRedaction": True, "widget": True}}
    )
    assert opted.features.document_analysis_redaction is True
    assert opted.features.widget is True
    with pytest.raises(ValidationFailedError) as caught:
        merge_settings(current, {"notARealSetting": True})
    assert caught.value.status == 422


def test_prepare_analysis_text_is_identity_for_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ar_domain.pii.analyzer._presidio", _fake_presidio)
    assert "P6.3" in prepare_analysis_text(EVIDENCE, aggressive=False)
    assert "P6.3" not in prepare_analysis_text(EVIDENCE, aggressive=True)


def test_installed_recogniser_keeps_grc_tokens() -> None:
    """Analysis keeps evidence even when the outbound profile masks it.

    CI does not download the spaCy model, so Presidio may leave the sentence
    unchanged. When the model is present, outbound replaces the spans and
    analysis must not.
    """
    sample = "Records stay in Ireland for 90 days under control P6.3."
    kept = redact(sample, profile="analysis")
    outbound = redact(sample, profile="outbound")
    assert "Ireland" in kept
    assert "90 days" in kept
    assert "P6.3" in kept
    if any(token in outbound for token in ("[LOCATION]", "[DATE_TIME]", "[US_DRIVER_LICENSE]")):
        assert "[LOCATION]" not in kept
        assert "[DATE_TIME]" not in kept
        assert "[US_DRIVER_LICENSE]" not in kept


def test_workspace_uuid_path_is_not_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool error must keep the sandbox path the model has to reuse."""
    path = "/var/ar-sandboxes/01a1ab39-7c4e-4b2a-8f11-abcdef012345/workspace/outputs/note.txt"
    guest = "/workspace/outputs/01a1ab39-7c4e-4b2a-8f11-abcdef012345.txt"
    sample = f"FileNotFoundError: {path} and {guest} ada@example.com"

    def spans(text: str, entities: frozenset[str]) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        for token, kind in (
            ("7c4e-4b2a-8f11", "us_driver_license"),
            ("ada@example.com", "email_address"),
        ):
            start = text.find(token)
            if start >= 0 and kind in entities:
                found.append(
                    {"entity": kind, "start": start, "end": start + len(token), "score": 1.0}
                )
        return found

    monkeypatch.setattr("ar_domain.pii.analyzer._presidio", spans)
    kept = redact(sample, profile="outbound")
    assert path in kept
    assert guest in kept
    assert "[US_DRIVER_LICENSE]" not in kept
    assert "ada@example.com" not in kept
    assert "[EMAIL_ADDRESS]" in kept
    store = demo_store()
    cleaned, _flag = apply_result_safety(
        store, sample, open_world=False, analysis=False, tenant_id=demo_id("tenant")
    )
    assert path in cleaned
    assert "[US_DRIVER_LICENSE]" not in cleaned


def test_agent_mask_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ar_domain.pii.analyzer._presidio", _fake_presidio)
    store: Any = demo_store()
    tenant = demo_id("tenant")
    version_id = uuid.uuid4()
    store.versions[version_id] = {"definition": {"safety": {"pii_masking": True}}}
    masked, _flag = apply_result_safety(
        store,
        EVIDENCE,
        open_world=True,
        analysis=True,
        tenant_id=tenant,
        agent_version_id=version_id,
    )
    assert "Ireland" not in masked
    assert "[LOCATION]" in masked
