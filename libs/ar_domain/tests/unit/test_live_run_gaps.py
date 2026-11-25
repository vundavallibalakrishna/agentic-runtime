"""Regressions from the live GRC pack run.

Label: unit
"""

from __future__ import annotations

import pytest

from ar_domain.agents.access import Actor
from ar_domain.agents.packs import _apply_policies
from ar_domain.approvals.errors import StepUpRequiredError
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
