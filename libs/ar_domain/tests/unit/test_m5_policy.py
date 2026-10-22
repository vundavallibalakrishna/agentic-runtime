"""Policy evaluator, approval consumption and the OPA fixture cross-check."""

import json
import subprocess
import threading
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from ar_common.errors import ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.approvals.service import ApprovalBook
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.policy.engine import consume_granted, evaluate_call
from ar_domain.policy.logic import evaluate, fallback

_ROOT = Path(__file__).resolve().parents[4]


def _actor(user: str = "admin") -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id(user),
        permissions=PERMISSION_KEYS,
        display_name=user,
    )


def test_desk_owner_is_the_builder() -> None:
    store = ChatService()
    desk = next(row for row in store.agents.values() if row.get("slug") == "desk")
    assert desk["owner_user_id"] == demo_id("builder")


def test_fallback_allows_builtins_and_deny_rules() -> None:
    policy_input = {
        "tool": {"qualified_name": "knowledge.search", "risk_class": "R0"},
        "args": {},
    }
    assert fallback(policy_input, [])["decision"] == "allow"
    denied = fallback(
        {"tool": {"qualified_name": "petstore.create_pet", "risk_class": "W2"}, "args": {}},
        [{"id": "d", "effect": "deny", "message": "no", "match": {}}],
    )
    assert denied["reasons"] == ["no"]
    closed = fallback(
        {"tool": {"qualified_name": "petstore.create_pet", "risk_class": "W2"}, "args": {}},
        [],
    )
    assert closed["reasons"] == ["policy_unavailable"]


def test_fixtures_agree_with_opa() -> None:
    for path in sorted((_ROOT / "policies" / "fixtures").glob("*.json")):
        document = json.loads(path.read_text())  # noqa: TID251
        sample = document["input"]
        rules = list(sample.get("rules") or [])
        settings = dict(sample.get("settings") or {})
        got = evaluate(sample, rules, settings)
        assert got["decision"] == document["expect"]["decision"]
        assert got["reasons"] == document["expect"]["reasons"]
        completed = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "opa",
                "eval",
                "-f",
                "raw",
                "-d",
                str(_ROOT / "policies" / "rego"),
                "-I",
                "data.ar.policy.decision",
            ],
            input=json.dumps(sample),
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        remote = json.loads(completed.stdout)  # noqa: TID251
        assert remote["decision"] == got["decision"]
        assert remote["reasons"] == got["reasons"]


def test_one_approval_is_consumed_once() -> None:
    store = ChatService()
    approval_id = new_id()
    store.approvals[approval_id] = {
        "id": approval_id,
        "status": "approved",
        "args_hash": "abc",
        "consumed_at": None,
    }
    mismatch = consume_granted(store, {"approval_id": approval_id, "args_hash": "other"})
    assert mismatch == "approval_invalid"
    results: list[str | None] = []

    def once() -> None:
        results.append(consume_granted(store, {"approval_id": approval_id, "args_hash": "abc"}))

    threads = [threading.Thread(target=once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count(None) == 1
    assert results.count("approval_invalid") == 1


def test_eval_runs_do_not_execute_writes() -> None:
    store = ChatService()
    run_id = new_id()
    store.runs[run_id] = {"id": run_id, "eval_context": True, "tenant_id": demo_id("tenant")}
    version = next(row for row in store.tool_versions.values() if row.get("name") == "create_pet")
    tool = store.tool_defs[version["tool_id"]]
    server_version = store.tool_server_versions[version["tool_server_version_id"]]
    server = store.tool_servers[server_version["tool_server_id"]]
    decision = evaluate_call(
        store,
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "run_id": run_id,
            "agent_id": None,
            "arguments": {"body": {"name": "Fido"}},
        },
        version,
        tool,
        server,
    )
    assert decision["decision"] == "deny"
    assert "eval runs do not execute writes" in decision["reasons"]


def test_owner_cannot_approve_and_self_grant_is_rejected() -> None:
    store = ChatService()
    desk = next(row for row in store.agents.values() if row.get("slug") == "desk")
    approval_id = new_id()
    store.approvals[approval_id] = {
        "id": approval_id,
        "tenant_id": demo_id("tenant"),
        "status": "pending",
        "agent_id": desk["id"],
        "requested_for_user_id": demo_id("admin"),
        "args_hash": "abc",
        "risk_class": "W2",
        "four_eyes": False,
        "step_up_required": False,
        "required_approvals": 1,
        "approver_rule": {"mode": "agent_owner", "groups": [], "users": []},
        "qualified_name": "petstore.create_pet",
        "arguments": {},
        "policy_reasons": [],
        "created_at": utcnow(),
        "expires_at": utcnow() + timedelta(hours=1),
    }
    builder = _actor("builder")
    with pytest.raises(ValidationFailedError, match="sod_violation"):
        ApprovalBook(store).decide(
            builder,
            approval_id,
            {"decision": "approve", "args_hash": "abc"},
            stepped_up=True,
        )
    tool = next(row for row in store.tool_defs.values() if row.get("name") == "create_pet")
    routine_id = uuid.uuid4()
    store.routines[routine_id] = {"id": routine_id, "owner_user_id": demo_id("admin")}
    with pytest.raises(ValidationFailedError, match="sod_self_approval"):
        ApprovalBook(store).grant_standing(
            _actor(),
            {
                "tool_id": tool["id"],
                "routine_id": routine_id,
                "expires_at": utcnow() + timedelta(days=1),
            },
        )
