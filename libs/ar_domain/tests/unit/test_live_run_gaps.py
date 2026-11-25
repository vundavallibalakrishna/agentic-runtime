"""Regressions from the live GRC pack run.

Label: unit
"""

from __future__ import annotations

import pytest

from ar_common.errors import ArError
from ar_domain.agents.access import Actor
from ar_domain.agents.packs import PackService, _apply_policies
from ar_domain.approvals.errors import StepUpRequiredError
from ar_domain.bundles.import_ import import_bundle
from ar_domain.chat.service import demo_id
from ar_testing.demo import demo_store

_POLICY_MANIFEST: dict[str, object] = {
    "metadata": {"id": "document_extraction"},
    "spec": {
        "resources": [
            {
                "kind": "Agent",
                "metadata": {"slug": "document-extraction"},
                "spec": {"settings": {"approvalGroup": "reviewers"}},
            },
            {
                "kind": "Policy",
                "metadata": {"name": "Results"},
                "spec": {
                    "document": {
                        "rules": [
                            {
                                "id": "extract",
                                "effect": "require_approval",
                                "match": {"tools": ["documents.extract"]},
                                "approval": {
                                    "approvers": {
                                        "mode": "group",
                                        "groups": ["{{approvalGroup}}"],
                                    }
                                },
                            }
                        ]
                    }
                },
            },
        ]
    },
}


def test_a_stepped_up_session_can_activate_a_pack_policy() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    session = Actor(tenant, demo_id("admin"), frozenset(), auth_method="session")
    with pytest.raises(StepUpRequiredError):
        _apply_policies(store, session, _POLICY_MANIFEST, stepped_up=False)
    assert [row for row in store.policies.values() if row.get("status") == "active"] == []
    _apply_policies(store, session, _POLICY_MANIFEST, stepped_up=True)
    active = [row for row in store.policies.values() if row.get("status") == "active"]
    assert len(active) == 1


def _agent(settings: object, schema: object) -> dict[str, object]:
    return {
        "kind": "Agent",
        "metadata": {"slug": "scanner", "name": "Scanner"},
        "spec": {
            "persona": {"displayName": "Scanner"},
            "instructions": "Scan the sources named in settings.",
            "settingsSchema": schema,
            "settings": settings,
        },
    }


def _pack(resources: list[dict[str, object]]) -> dict[str, object]:
    return {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {"id": "notes", "version": "1.0.0", "name": "Notes"},
        "spec": {"resources": resources},
    }


def test_an_agent_resource_keeps_settings_that_match_its_schema() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    actor = Actor(
        tenant, demo_id("admin"), frozenset({"packs:manage", "agents:create"})
    )
    schema = {
        "type": "object",
        "required": ["sources"],
        "properties": {"sources": {"type": "array"}},
    }
    resource = _agent({"sources": ["https://example.test/feed"]}, schema)
    imported = import_bundle(
        store, actor, {"spec": {"resources": [resource]}}, dry_run=False
    )
    assert imported["results"][0]["action"] == "create"
    agent = next(row for row in store.agents.values() if row.get("slug") == "scanner")
    version = store.versions[agent["draft_version_id"]]
    definition = version["definition"]
    assert "settings" not in definition
    assert "settingsSchema" not in definition
    installed = PackService(store).install(
        actor, _pack([resource]), signature=None, key_id=None
    )
    assert installed["status"] == "installed"


def test_pack_install_fails_when_agent_settings_do_not_match() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    actor = Actor(tenant, demo_id("admin"), frozenset({"packs:manage"}))
    schema = {
        "type": "object",
        "required": ["sources"],
        "properties": {"sources": {"type": "array"}},
        "additionalProperties": False,
    }
    resource = _agent({"sources": "not-a-list"}, schema)
    with pytest.raises(ArError, match="scanner"):
        PackService(store).install(actor, _pack([resource]), signature=None, key_id=None)
    assert store.packs == {}
    assert not any(row.get("slug") == "scanner" for row in store.agents.values())
