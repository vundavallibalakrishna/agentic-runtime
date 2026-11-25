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
    store = demo_store()
    tenant = demo_id("tenant")
    store.tenant_settings[tenant] = {"documents": {"extractionReviewGroup": "reviewers"}}
    actor = Actor(tenant, demo_id("admin"), frozenset())
    _apply_policies(
        store,
        actor,
        {
            "spec": {
                "resources": [
                    {
                        "kind": "Policy",
                        "metadata": {"name": "Results"},
                        "spec": {
                            "document": {
                                "rules": [
                                    {
                                        "approval": {
                                            "approvers": {
                                                "mode": "group",
                                                "groups": ["{{approvalGroup}}"],
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                    }
                ]
            }
        },
    )
    version = next(iter(store.policy_versions.values()))
    groups = version["document"]["rules"][0]["approval"]["approvers"]["groups"]
    assert groups == ["reviewers"]
