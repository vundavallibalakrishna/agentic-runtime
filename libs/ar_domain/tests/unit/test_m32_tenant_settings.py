"""Tenant settings are read for the calling tenant only. Task: M32-T02."""

import uuid
from typing import TYPE_CHECKING

from ar_domain.identity.tenant_settings import section, settings_for
from ar_domain.pii.analyzer import Masking, _presidio, maskable_entities, redact
from ar_domain.pii.recognizers_in import find_indian
from ar_domain.records.vault import EvidenceBook
from ar_domain.security.guardrails import apply_result_safety
from ar_domain.tools.handlers import dispatch
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

PHONE = "call 9876543210 now"


def _store() -> tuple[ChatService, uuid.UUID, uuid.UUID]:
    store = demo_store()
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    store.tenant_settings[tenant_a] = {"features": {"pii_redaction": False}}
    store.tenant_settings[tenant_b] = {"features": {"pii_redaction": True}}
    return store, tenant_a, tenant_b


def _entities(text: str) -> list[str]:
    """Every kind either recogniser reports for ``text``."""
    everything = frozenset(maskable_entities())
    found = (*find_indian(text), *_presidio(text, everything))
    return sorted({str(span["entity"]).lower() for span in found})


def test_settings_for_never_returns_another_tenants_row() -> None:
    store, tenant_a, _ = _store()
    assert settings_for(store, tenant_a)["features"] == {"pii_redaction": False}
    assert settings_for(store, uuid.uuid4()) == {}
    assert settings_for(store, None) == {}
    assert settings_for(store, "not-a-uuid") == {}
    assert settings_for(store, str(tenant_a)) == settings_for(store, tenant_a)
    assert section({"a": {"b": {"c": 1}}}, "a", "b") == {"c": 1}
    assert section({"a": 3}, "a", "b") == {}


def test_redaction_follows_the_calling_tenant_only() -> None:
    store, tenant_a, tenant_b = _store()
    off, _ = apply_result_safety(store, PHONE, open_world=False, tenant_id=tenant_a)
    on, _ = apply_result_safety(store, PHONE, open_world=False, tenant_id=tenant_b)
    unknown, _ = apply_result_safety(store, PHONE, open_world=False, tenant_id=uuid.uuid4())
    no_tenant, _ = apply_result_safety(store, PHONE, open_world=False, tenant_id=None)
    assert off == PHONE
    assert "9876543210" not in on
    assert "9876543210" not in unknown, "a tenant without a row keeps the safe default"
    assert "9876543210" not in no_tenant, "no tenant must not borrow tenant A's opt-out"


def test_tenant_can_skip_entity_types() -> None:
    assert "9876543210" not in redact(PHONE)
    found = _entities(PHONE)
    assert found, "the fixture must trip at least one recogniser"
    assert redact(PHONE, masking=Masking().without(frozenset(found))) == PHONE
    store, _, tenant_b = _store()
    store.tenant_settings[tenant_b]["privacy"] = {"redaction_skip_entities": found}
    kept, _ = apply_result_safety(store, PHONE, open_world=False, tenant_id=tenant_b)
    assert kept == PHONE
    masked, _ = apply_result_safety(store, PHONE, open_world=False, tenant_id=uuid.uuid4())
    assert "9876543210" not in masked


def test_web_fetch_feature_is_read_per_tenant() -> None:
    store = demo_store()
    tenant_on, tenant_off = uuid.uuid4(), uuid.uuid4()
    store.tenant_settings[tenant_on] = {"features": {"web_fetch": True}}
    store.tenant_settings[tenant_off] = {"features": {"web_fetch": False}}
    url = "https://example.com/"
    denied = dispatch(store, "builtin://web", "fetch", {"url": url, "_tenant_id": tenant_off}, None)
    assert denied["code"] == "feature_disabled"
    allowed = dispatch(store, "builtin://web", "fetch", {"url": url, "_tenant_id": tenant_on}, None)
    assert allowed.get("code") != "feature_disabled"
    anonymous = dispatch(store, "builtin://web", "fetch", {"url": url}, None)
    assert anonymous["code"] == "feature_disabled", "no tenant means the default, which is off"


def test_evidence_tsa_requirement_is_the_actors_tenant() -> None:
    store = demo_store()
    tsa_down, plain = uuid.uuid4(), uuid.uuid4()
    store.tenant_settings[tsa_down] = {"evidence": {"tsa_enabled": True, "tsa_ok": False}}
    store.tenant_settings[plain] = {}
    book = EvidenceBook(store)
    assert book._tsa_required_and_down(tsa_down) is True
    assert book._tsa_required_and_down(plain) is False
    assert book._tsa_required_and_down(uuid.uuid4()) is False
