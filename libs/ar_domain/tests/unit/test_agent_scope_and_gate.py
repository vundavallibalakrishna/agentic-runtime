"""Skipping the eval gate, staying inside bound collections, and masking attached file text."""

from __future__ import annotations

import uuid

import pytest

from ar_common.errors import ArError
from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import demo_id
from ar_domain.evals.book import EvalBook
from ar_domain.files.attachments import Attachment
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.memory.session import _safe, _safe_text
from ar_domain.tools.handlers import _bound_collections, _document_within, _within
from ar_testing.demo import demo_store


def _actor(*, without: str = "") -> Actor:
    permissions = frozenset(key for key in PERMISSION_KEYS if key != without)
    return Actor(demo_id("tenant"), demo_id("admin"), permissions, display_name="Admin")


def _gated_agent() -> tuple[object, AgentLifecycle, uuid.UUID]:
    store = demo_store()
    life = AgentLifecycle(store)
    created = life.create(_actor(), slug="gated", name="Gated", description="gate")
    agent_id = uuid.UUID(str(created["id"]))
    EvalBook(store).create_suite(
        _actor(),
        {"name": "Gate", "kind": "functional", "agent_id": agent_id, "gate": {"required": True}},
    )
    return store, life, agent_id


def test_skipping_a_required_suite_needs_the_permission_the_spec_names() -> None:
    store, life, agent_id = _gated_agent()
    with pytest.raises(ArError) as refused:
        life.publish(_actor(without="agents:manage_all"), agent_id, skip_eval_gate=True)
    assert refused.value.code.value == "forbidden"
    assert "agents:manage_all" in str(refused.value)
    assert store.agents[agent_id]["status"] != "published"  # type: ignore[attr-defined]
    life.publish(_actor(), agent_id, change_note="reviewed by hand", skip_eval_gate=True)
    assert store.agents[agent_id]["status"] == "published"  # type: ignore[attr-defined]
    entry = next(
        row
        for row in reversed(store.audit_log)  # type: ignore[attr-defined]
        if row["action"] == "agent.published"
    )
    assert entry["detail"]["eval_gate_skipped"] is True


def test_the_flag_takes_the_permission_even_with_no_required_suite() -> None:
    store = demo_store()
    life = AgentLifecycle(store)
    created = life.create(_actor(), slug="plain", name="Plain", description="no gate")
    agent_id = uuid.UUID(str(created["id"]))
    with pytest.raises(ArError):
        life.publish(_actor(without="agents:manage_all"), agent_id, skip_eval_gate=True)
    life.publish(_actor(), agent_id, skip_eval_gate=True)
    entry = next(row for row in reversed(store.audit_log) if row["action"] == "agent.published")
    # Nothing was passed over, so the entry does not say a gate was skipped.
    assert entry["detail"]["eval_gate_skipped"] is False


def test_a_gate_that_passed_publishes_without_asking_for_the_skip_permission() -> None:
    store, life, agent_id = _gated_agent()
    draft = store.agents[agent_id]["draft_version_id"]  # type: ignore[attr-defined]
    life.complete_gated_publish(draft, passed=False)
    assert store.agents[agent_id]["status"] != "published"  # type: ignore[attr-defined]
    life.complete_gated_publish(draft, passed=True)
    assert store.agents[agent_id]["status"] == "published"  # type: ignore[attr-defined]
    entry = next(
        row
        for row in reversed(store.audit_log)  # type: ignore[attr-defined]
        if row["action"] == "agent.published"
    )
    assert entry["detail"]["eval_gate_skipped"] is False


class _Store:
    def __init__(self) -> None:
        self.versions: dict[uuid.UUID, dict[str, object]] = {}
        self.knowledge_collections: dict[uuid.UUID, dict[str, object]] = {}
        self.tenant_settings: dict[uuid.UUID, dict[str, object]] = {}


def test_an_agent_that_binds_collections_reads_those_and_no_others() -> None:
    store = _Store()
    bound_version, free_version = uuid.uuid4(), uuid.uuid4()
    store.versions[bound_version] = {"definition": {"knowledge": {"collections": ["Sales"]}}}
    store.versions[free_version] = {"definition": {"knowledge": {"collections": []}}}
    sales, payroll = uuid.uuid4(), uuid.uuid4()
    store.knowledge_collections = {
        sales: {"id": sales, "slug": "sales"},
        payroll: {"id": payroll, "slug": "payroll"},
    }
    rows = [{"id": sales, "slug": "sales"}, {"id": payroll, "slug": "payroll"}]
    bound = _bound_collections(store, {"_agent_version_id": bound_version})
    assert bound == {"sales"}
    assert [row["slug"] for row in _within(rows, bound)] == ["sales"]
    assert _document_within(store, {"collection_id": sales}, bound) is True
    assert _document_within(store, {"collection_id": str(payroll)}, bound) is False
    assert _document_within(store, {"collection_id": uuid.uuid4()}, bound) is False
    # An agent that names no collection reads what the person may read.
    free = _bound_collections(store, {"_agent_version_id": free_version})
    assert free is None
    assert _within(rows, free) == rows
    assert _document_within(store, {"collection_id": payroll}, free) is True
    assert _bound_collections(store, {}) is None


def test_attached_file_text_is_masked_when_the_agent_asks_for_masking() -> None:
    store = _Store()
    tenant, masked, plain = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    store.versions[masked] = {"definition": {"safety": {"pii_masking": True}}}
    store.versions[plain] = {"definition": {"safety": {"pii_masking": False}}}
    text = "[p1-s0] The supplier contact is Jane Doe, jane.doe@example.com."
    shown = _safe_text(store, {"tenant_id": tenant, "agent_version_id": masked}, text)
    assert "jane.doe@example.com" not in shown
    assert "[p1-s0]" in shown
    kept = _safe_text(store, {"tenant_id": tenant, "agent_version_id": plain}, text)
    assert "[p1-s0]" in kept
    item = Attachment(
        file_id=uuid.uuid4(),
        message_id=None,
        name="contact.md",
        mime_type="text/markdown",
        size_bytes=64,
        path="inputs/contact.md",
        excerpt=text,
    )
    safe = _safe(store, {"tenant_id": tenant, "agent_version_id": masked}, item)
    assert "jane.doe@example.com" not in safe.line()
    assert "contact.md" in safe.line()
    empty = Attachment(uuid.uuid4(), None, "a.csv", "text/csv", 1, "inputs/a.csv")
    assert _safe(store, {"tenant_id": tenant}, empty) is empty
    assert _safe_text(store, None, text) == text
