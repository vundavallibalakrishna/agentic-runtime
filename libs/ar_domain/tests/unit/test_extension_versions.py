"""Pack row versions, the audit of a put, and a preparer who cannot approve.

Label: unit
"""

from ar_domain.agents.access import Actor
from ar_domain.agents.packs import _apply_policies
from ar_domain.approvals.logic import can_decide
from ar_domain.chat.service import demo_id
from ar_domain.tools.extensions import dispatch_extensions
from ar_testing.demo import demo_store


def test_putting_again_raises_the_version_and_is_audited() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    first = dispatch_extensions(
        store,
        "put",
        {"_tenant_id": tenant, "packId": "scenario_runs", "bucket": "runs", "payload": {"n": 1}},
    )
    assert first["structured"]["version"] == 1
    second = dispatch_extensions(
        store,
        "put",
        {
            "_tenant_id": tenant,
            "packId": "scenario_runs",
            "bucket": "runs",
            "payload": {"n": 2},
            "id": first["structured"]["id"],
            "reason": "corrected",
        },
    )
    assert second["structured"]["version"] == 2
    assert store.audit_log[-1]["action"] == "extensions.put"
    assert store.audit_log[-1]["detail"]["reason"] == "corrected"


def test_put_and_list_stay_inside_the_tenant_and_the_pack() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    other = demo_id("other")
    first = dispatch_extensions(
        store,
        "put",
        {"_tenant_id": tenant, "packId": "scenario_runs", "bucket": "runs", "payload": {"n": 1}},
    )
    row_id = first["structured"]["id"]
    stolen = dispatch_extensions(
        store,
        "put",
        {
            "_tenant_id": other,
            "packId": "other_pack",
            "bucket": "runs",
            "payload": {"n": 9},
            "id": row_id,
        },
    )
    assert stolen["is_error"] is True
    hidden = dispatch_extensions(store, "get", {"_tenant_id": other, "id": row_id})
    assert hidden["is_error"] is True
    listed = dispatch_extensions(
        store, "list", {"_tenant_id": tenant, "packId": "scenario_runs", "bucket": "runs"}
    )
    assert len(listed["structured"]["rows"]) == 1
    empty = dispatch_extensions(store, "list", {"_tenant_id": other, "packId": "scenario_runs"})
    assert empty["structured"]["rows"] == []


def test_a_preparer_cannot_approve_their_own_four_eyes_result() -> None:
    store = demo_store()
    user = demo_id("admin")
    actor = Actor(demo_id("tenant"), user, frozenset({"approvals:decide"}))
    store.user_groups[user] = ["approvers"]
    approval = {
        "status": "pending",
        "four_eyes": True,
        "requested_for_user_id": user,
        "approver_rule": {"mode": "group", "groups": ["approvers"]},
    }
    assert can_decide(store, actor, approval) is False


def test_pack_policies_take_the_approver_group_from_settings() -> None:
    from ar_domain.policy.logic import rule_matches

    store = demo_store()
    tenant = demo_id("tenant")
    actor = Actor(tenant, demo_id("admin"), frozenset())
    manifest = {
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
    _apply_policies(store, actor, manifest)
    _apply_policies(store, actor, manifest)
    named = [row for row in store.policies.values() if row.get("name") == "Results"]
    assert len(named) == 1
    version = store.policy_versions[named[0]["active_version_id"]]
    rule = version["document"]["rules"][0]
    assert rule["approval"]["approvers"]["groups"] == ["reviewers"]
    assert rule["match"]["agents"] == ["document-extraction"]
    own = {
        "tool": {"qualified_name": "documents.extract"},
        "agent": {"slug": "document-extraction"},
    }
    other = {"tool": {"qualified_name": "documents.extract"}, "agent": {"slug": "assistant"}}
    assert rule_matches(rule, own) is True
    assert rule_matches(rule, other) is False
    assert any(
        row["action"] == "policy.created" and row.get("detail", {}).get("name") == "Results"
        for row in store.audit_log
    )
