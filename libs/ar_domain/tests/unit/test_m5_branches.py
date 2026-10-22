"""Branch coverage for the in-process policy and approval evaluators."""

import hashlib
import uuid
from datetime import timedelta

import pytest

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.approvals import models as approval_models
from ar_domain.approvals import repository as approval_repository
from ar_domain.approvals.errors import StepUpRequiredError
from ar_domain.approvals.logic import can_decide, consume_standing, render_preview
from ar_domain.approvals.reviews import ReviewBook
from ar_domain.approvals.service import ApprovalBook
from ar_domain.approvals.sod import SodBook
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.policy import models as policy_models
from ar_domain.policy import repository as policy_repository
from ar_domain.policy.engine import evaluate_call
from ar_domain.policy.logic import (
    enrich_time,
    evaluate,
    fallback,
    jsonpath_values,
    normalize_effect,
    predicate_holds,
)
from ar_domain.policy.service import PolicyBook
from ar_domain.rows import as_datetime, as_dict, as_int, as_list, as_uuid, as_uuid_or_none
from ar_mcp_gateway.approvals import book as gateway_book
from ar_mcp_gateway.policy import decide as gateway_decide

_SETTINGS = {
    "approvals": {"default_ttl_s": 86400},
    "security": {"require_step_up_for_w3": True, "require_step_up_for_signoff": True},
}


def _input(risk: str = "W2", name: str = "petstore.create_pet") -> dict[str, object]:
    return {
        "tenant_id": "t",
        "tool": {
            "qualified_name": name,
            "name": name.split(".", 1)[-1],
            "server_slug": "petstore",
            "risk_class": risk,
            "data_classification": "internal",
        },
        "agent": {"id": "a", "slug": "desk", "overrides": {}},
        "run": {"id": "r", "trigger": "chat", "channel": "web"},
        "user": {
            "id": "u",
            "groups": ["ops"],
            "teams": ["desk"],
            "attributes": {"site": "hq"},
        },
        "args": {"body": {"name": "Fido", "tags": ["a", "b"], "score": 3}},
        "time": enrich_time(utcnow()),
        "settings": _SETTINGS,
    }


def _actor(user: str = "admin") -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id(user),
        permissions=PERMISSION_KEYS,
        roles=frozenset({"tenant_admin"}),
        display_name=user,
    )


def test_models_import() -> None:
    assert policy_models.Policy.__tablename__ == "policies"
    assert approval_models.Approval.__tablename__ == "approvals"
    assert policy_repository.PolicyRepository.__name__
    assert approval_repository.ApprovalRepository.__name__


def test_row_helpers() -> None:
    assert as_int(True, 4) == 4
    assert as_int("x", 4) == 4
    assert as_uuid(str(demo_id("admin"))) == demo_id("admin")
    assert as_uuid_or_none(None) is None
    assert as_uuid_or_none("") is None
    assert as_uuid_or_none(demo_id("admin")) == demo_id("admin")
    assert as_dict("no") == {}
    assert as_list("no") == []
    assert as_datetime("no") is None
    assert as_datetime(utcnow()) is not None


def test_effects_and_argument_ops() -> None:
    assert normalize_effect("requireApproval") == "require_approval"
    assert normalize_effect("nope") == "deny"
    sample = _input()
    assert evaluate(sample, [], _SETTINGS)["decision"] == "require_approval"
    assert evaluate(_input("R0", "files.read"), [], _SETTINGS)["decision"] == "allow"
    assert evaluate(_input("W3", "petstore.delete_pet"), [], _SETTINGS)["decision"] == "deny"
    allow = {
        "id": "a",
        "effect": "allow",
        "match": {
            "tools": ["petstore.*"],
            "servers": ["petstore"],
            "risk_classes": ["W2"],
            "agents": ["desk"],
            "triggers": ["chat"],
            "channels": ["web"],
            "user_groups": ["ops"],
            "user_teams": ["desk"],
            "user_attributes": {"site": ["hq"]},
            "data_classifications": ["internal"],
        },
    }
    assert evaluate(sample, [allow], _SETTINGS)["decision"] == "allow"
    forced = dict(sample)
    forced["agent"] = {"slug": "desk", "overrides": {"create_pet": {"require_approval": "always"}}}
    assert evaluate(forced, [allow], _SETTINGS)["decision"] == "require_approval"
    deny = {"id": "d", "effect": "deny", "message": "no", "match": {"tools": ["*"]}}
    assert evaluate(sample, [deny, allow], _SETTINGS)["decision"] == "deny"
    first = {
        "id": "r1",
        "effect": "require_approval",
        "priority": 10,
        "policy_name": "a",
        "message": "ask",
        "approval": {
            "approvers": {"mode": "users", "users": ["u"], "groups": ["ops"]},
            "required_approvals": 2,
            "ttl_s": 120,
            "four_eyes": True,
        },
        "match": {"tools": ["petstore.create_pet"]},
    }
    second = {
        "id": "r2",
        "effect": "require_approval",
        "priority": 50,
        "policy_name": "b",
        "approval": {"requiredApprovals": 1, "ttlS": 90, "stepUp": True},
        "match": {"tools": ["petstore.create_pet"]},
    }
    merged = evaluate(sample, [second, first], _SETTINGS)
    assert merged["approval"]["required_approvals"] == 2
    assert merged["approval"]["ttl_s"] == 90
    w3 = _input("W3", "petstore.delete_pet")
    upgraded = evaluate(w3, [{"id": "w", "effect": "allow", "match": {}}], _SETTINGS)
    assert upgraded["approval"]["approvers"]["mode"] == "agent_owner"
    named = evaluate(
        w3,
        [
            {
                "id": "n",
                "effect": "require_approval",
                "message": "confirm",
                "approval": {"approvers": {"mode": "users", "users": ["approver"]}},
                "match": {},
            }
        ],
        _SETTINGS,
    )
    assert named["approval"]["approvers"]["mode"] == "users"
    assert named["approval"]["four_eyes"] is True
    window = {
        "id": "t",
        "effect": "deny",
        "message": "closed",
        "match": {
            "time_window": {
                "timezone": "UTC",
                "days": ["MON"],
                "from": "00:00",
                "to": "23:59",
            }
        },
    }
    evaluate(sample, [window], _SETTINGS)
    overnight = {
        "id": "n",
        "effect": "deny",
        "message": "night",
        "match": {"timeWindow": {"timezone": "UTC", "from": "22:00", "to": "06:00"}},
    }
    evaluate(sample, [overnight], _SETTINGS)
    missing_zone = {
        "id": "z",
        "effect": "deny",
        "match": {"time_window": {"timezone": "Mars", "from": "00:00", "to": "01:00"}},
    }
    assert evaluate(sample, [missing_zone], _SETTINGS)["decision"] == "require_approval"
    bad_args = {
        "id": "b",
        "effect": "deny",
        "match": {"args": ["nope", {"path": "$.missing", "op": "eq", "value": 1}]},
    }
    assert evaluate(sample, [bad_args], _SETTINGS)["decision"] == "require_approval"


def test_predicates_and_paths() -> None:
    document = {
        "body": {"name": "Fido", "tags": ["a", "b"], "score": 3, "url": "https://pets.dev/a"}
    }
    assert jsonpath_values(document, "$.body.tags[*]") == ["a", "b"]
    assert jsonpath_values(document, "$.body.tags[0]") == ["a"]
    assert jsonpath_values(document, "$.body.tags[9]") == []
    assert jsonpath_values(document, "nope") == []
    assert predicate_holds("eq", ["Fido"], "Fido", starred=False)
    assert predicate_holds("neq", ["Fido"], "Rex", starred=False)
    assert predicate_holds("in", ["a"], ["a", "b"], starred=False)
    assert predicate_holds("not_in", ["z"], ["a"], starred=False)
    assert predicate_holds("matches", ["Fido"], "^Fi", starred=False)
    assert predicate_holds("not_matches", ["Fido"], "^Z", starred=False)
    assert predicate_holds("matches", ["Fido"], "a" * 201, starred=False) is False
    assert predicate_holds("matches", ["Fido"], "(", starred=False) is False
    assert predicate_holds("domain_in", ["https://pets.dev/a"], ["pets.dev"], starred=False)
    assert predicate_holds("not_domain_in", ["user@other.dev"], ["pets.dev"], starred=False)
    assert predicate_holds("gt", [4], 3, starred=False)
    assert predicate_holds("gte", [3], 3, starred=False)
    assert predicate_holds("lt", [1], 3, starred=False)
    assert predicate_holds("lte", [3], 3, starred=False)
    assert predicate_holds("gt", [True], 1, starred=False) is False
    assert predicate_holds("len_gt", ["abcd"], 2, starred=False)
    assert predicate_holds("exists", ["x"], None, starred=False)
    assert predicate_holds("not_exists", [], None, starred=False)
    assert predicate_holds("eq", ["a", "b"], "b", starred=True)
    assert predicate_holds("neq", ["a", "b"], "a", starred=True)
    assert predicate_holds("other", ["a"], "a", starred=False) is False
    assert predicate_holds("eq", [], "a", starred=False) is False
    closed = fallback(
        {"tool": {"qualified_name": "files.read", "risk_class": "R0"}},
        [],
    )
    assert closed["decision"] == "allow"


def test_standing_grant_and_w3_block() -> None:
    store = ChatService()
    actor = _actor()
    book = ApprovalBook(store)
    tool = next(row for row in store.tool_defs.values() if row.get("name") == "create_pet")
    agent = next(row for row in store.agents.values() if row.get("slug") == "desk")
    granted = book.grant_standing(
        actor,
        {
            "tool_id": tool["id"],
            "agent_id": agent["id"],
            "expires_at": utcnow() + timedelta(days=7),
            "max_uses": 2,
            "argument_constraints": [{"path": "$.body.name", "op": "eq", "value": "Fido"}],
        },
    )
    assert book.list_standing(actor)
    version = next(
        row
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "petstore.create_pet"
    )
    request = {
        "tenant_id": demo_id("tenant"),
        "user_id": actor.user_id,
        "agent_id": agent["id"],
        "run_id": None,
        "arguments": {"body": {"name": "Fido"}},
        "risk_class": "W2",
    }
    assert consume_standing(store, request, tool) == str(granted["id"])
    deleted = next(row for row in store.tool_defs.values() if row.get("name") == "delete_pet")
    with pytest.raises(ValidationFailedError):
        book.grant_standing(
            actor,
            {
                "tool_id": deleted["id"],
                "agent_id": agent["id"],
                "expires_at": utcnow() + timedelta(days=1),
            },
        )
    with pytest.raises(ValidationFailedError):
        book.grant_standing(
            actor,
            {"tool_id": tool["id"], "expires_at": utcnow() + timedelta(days=1)},
        )
    with pytest.raises(ValidationFailedError):
        book.grant_standing(
            actor,
            {
                "tool_id": tool["id"],
                "agent_id": agent["id"],
                "expires_at": utcnow() + timedelta(days=200),
            },
        )
    book.revoke_standing(actor, uuid.UUID(str(granted["id"])))
    server = next(iter(store.tool_servers.values()))
    decision = evaluate_call(store, request, version, tool, server)
    assert decision["decision"] in {"allow", "require_approval", "deny"}
    store.opa_url = "http://127.0.0.1:9"
    missed = evaluate_call(store, request, version, tool, server)
    assert missed["decision"] in {"allow", "deny", "require_approval"}


def test_reviews_and_sod_paths() -> None:
    store = ChatService()
    actor = _actor()
    reviews = ReviewBook(store)
    queue = reviews.create_queue(
        actor,
        {
            "slug": "extra",
            "name": "Extra",
            "subject_type": "artifact",
            "levels": [{"level": 1, "required_count": 1, "step_up": True, "role_key": ""}],
        },
    )
    reviews.patch_queue(actor, uuid.UUID(str(queue["id"])), {"name": "Extra review"})
    subject = uuid.uuid4()
    digest = __import__("hashlib").sha256(f"artifact:{subject}".encode()).hexdigest()
    preparer = _actor("builder")
    opened = reviews.open_item(
        preparer,
        {
            "queue_id": queue["id"],
            "subject_type": "artifact",
            "subject_id": str(subject),
            "content_hash": digest,
            "statement_text": "I reviewed it.",
        },
    )
    assert reviews.list_items(preparer, scope="prepared", status=None, queue_id=None)
    with pytest.raises(ValidationFailedError):
        reviews.open_item(
            actor,
            {
                "queue_id": queue["id"],
                "subject_type": "artifact",
                "subject_id": str(uuid.uuid4()),
                "content_hash": "nope",
                "statement_text": "I reviewed it.",
            },
        )
    detail = reviews.get_item(actor, uuid.UUID(str(opened["id"])))
    decided = reviews.decide(
        actor,
        uuid.UUID(str(opened["id"])),
        {
            "decision": "approve",
            "content_hash": detail["content_hash"],
            "statement_hash": detail["statement_hash"],
            "comment": "ok",
        },
        stepped_up=True,
    )
    assert decided["status"] in {"signed", "in_review", "approved"}
    sod = SodBook(store)
    checked = sod.check(
        actor,
        {
            "action": "signoff",
            "signer_principal_id": str(actor.user_id),
            "preparer_principal_id": str(demo_id("builder")),
        },
    )
    assert "allowed" in checked
    created = sod.create_constraint(
        actor, {"role_a": "author", "role_b": "checker", "applies_to": "both"}
    )
    assert sod.list_constraints(actor)
    sod.delete_constraint(actor, uuid.UUID(str(created["id"])))
    with pytest.raises(NotFoundError):
        sod.delete_constraint(actor, uuid.uuid4())
    limited = Actor(demo_id("tenant"), demo_id("member"), frozenset(), roles=frozenset())
    with pytest.raises(ForbiddenError):
        ApprovalBook(store).list_standing(limited)
    approval = {
        "status": "pending",
        "four_eyes": True,
        "requested_for_user_id": actor.user_id,
        "approver_rule": {"mode": "requester"},
    }
    assert can_decide(store, actor, approval) is False
    preview = render_preview(
        {
            "title": "Pet {{$.body.name}}",
            "summary": "named {{$.body.name}}",
            "fields": [{"label": "Name", "path": "$.body.name"}, "skip"],
            "diff": {"before_path": "$.before", "after_path": "$.after"},
            "links": [],
        },
        {"body": {"name": "Fido"}, "before": "a", "after": "b"},
        title="Pet",
    )
    assert "Fido" in str(preview["title"])
    render_preview(None, {"body": {"name": "Fido"}}, title="Pet")
    with pytest.raises(ConflictError):
        reviews.create_queue(
            actor,
            {
                "slug": "extra",
                "name": "Again",
                "subject_type": "artifact",
                "levels": [{"level": 1}],
            },
        )


def test_expire_cancel_edit_and_bulk() -> None:
    store = ChatService()
    actor = _actor()
    book = ApprovalBook(store)
    run_id = new_id()
    store.events[run_id] = []
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": actor.tenant_id,
        "user_id": actor.user_id,
        "status": "waiting_approval",
        "conversation_id": None,
        "assistant_message_id": None,
        "pending_approval": {},
    }
    pending = book.create_pending(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        run_id=run_id,
        agent_id=None,
        tool_call_id=new_id(),
        qualified_name="petstore.create_pet",
        risk_class="W2",
        args_hash="hash-1",
        arguments={"body": {"name": "Fido"}},
        requirement={"approvers": {"mode": "requester"}, "ttl_s": 120},
        reasons=["ask"],
        preview={"title": "Pet", "summary": "Fido"},
    )
    store.runs[run_id]["pending_approval"] = {
        "approval_id": pending["id"],
        "model_call_id": "m1",
        "arguments": {"body": {"name": "Fido"}},
        "args_hash": "hash-1",
    }
    edited = book.decide(
        actor,
        pending["id"],
        {
            "decision": "approve",
            "args_hash": "hash-1",
            "arguments": {"body": {"name": "Rex"}},
            "comment": "rename",
        },
        stepped_up=True,
    )
    assert edited["status"] in {"pending", "rejected", "approved"}
    expiring = book.create_pending(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        run_id=None,
        agent_id=None,
        tool_call_id=new_id(),
        qualified_name="petstore.create_pet",
        risk_class="W2",
        args_hash="hash-2",
        arguments={},
        requirement={"approvers": {"mode": "requester"}},
        reasons=[],
        preview={"title": "Pet"},
    )
    expiring["expires_at"] = utcnow() - timedelta(seconds=5)
    assert book.expire_due() >= 1
    cancelling = book.create_pending(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        run_id=run_id,
        agent_id=None,
        tool_call_id=new_id(),
        qualified_name="petstore.create_pet",
        risk_class="W2",
        args_hash="hash-3",
        arguments={},
        requirement={"approvers": {"mode": "requester"}},
        reasons=[],
        preview={"title": "Pet"},
    )
    store.runs[run_id]["status"] = "waiting_approval"
    store.runs[run_id]["pending_approval"] = {
        "approval_id": cancelling["id"],
        "model_call_id": "m2",
    }
    book.cancel(actor, cancelling["id"])
    reviews = ReviewBook(store)
    queues = reviews.list_queues(actor)
    subject = uuid.uuid4()
    digest = __import__("hashlib").sha256(f"artifact:{subject}".encode()).hexdigest()
    opened = reviews.open_item(
        _actor("builder"),
        {
            "queue_id": queues[0]["id"],
            "subject_type": "artifact",
            "subject_id": str(subject),
            "content_hash": digest,
            "statement_text": "I reviewed it.",
        },
    )
    bulk = reviews.bulk(
        actor,
        {
            "decision": "approve",
            "comment": "batch",
            "items": [
                {
                    "review_item_id": opened["id"],
                    "content_hash": opened["content_hash"],
                    "statement_hash": opened["statement_hash"],
                },
                "skip",
                {"review_item_id": str(uuid.uuid4())},
            ],
        },
        stepped_up=True,
    )
    assert bulk["results"]


def _digest(kind: str, subject: uuid.UUID) -> str:
    return hashlib.sha256(f"{kind}:{subject}".encode()).hexdigest()


def test_reviews_queues_signoff_and_sod() -> None:
    store = ChatService()
    admin = _actor()
    builder = _actor("builder")
    reviews = ReviewBook(store)
    with pytest.raises(ValidationFailedError):
        reviews.create_queue(admin, {"slug": "empty", "subject_type": "artifact", "levels": []})
    with pytest.raises(ValidationFailedError):
        reviews.create_queue(admin, {"slug": "bad", "subject_type": "invoice", "levels": [{}]})
    queue = reviews.create_queue(
        admin,
        {
            "slug": "two-level",
            "name": "Two level",
            "subject_type": "artifact",
            "levels": [
                {"level": 1, "required_count": 1, "role_key": "approver"},
                {"level": 2, "required_count": 1, "step_up": True},
            ],
            "statement_template": "Reviewed {title}",
        },
    )
    patched = reviews.patch_queue(
        admin,
        uuid.UUID(str(queue["id"])),
        {"name": "Renamed", "levels": queue["levels"], "statement_template": "Signed {title}"},
    )
    assert patched["name"] == "Renamed"
    assert reviews.get_queue(admin, uuid.UUID(str(queue["id"])))["slug"] == "two-level"
    spare = reviews.create_queue(
        admin,
        {"slug": "spare", "name": "Spare", "subject_type": "file", "levels": [{"level": 1}]},
    )
    reviews.delete_queue(admin, uuid.UUID(str(spare["id"])))
    with pytest.raises(NotFoundError):
        reviews.get_queue(admin, uuid.uuid4())

    subject = uuid.uuid4()
    with pytest.raises(ValidationFailedError):
        reviews.open_item(
            builder,
            {
                "queue_id": queue["id"],
                "subject_type": "artifact",
                "subject_id": str(subject),
                "content_hash": "wrong",
                "statement_text": "I reviewed it.",
            },
        )
    opened = reviews.open_item(
        builder,
        {
            "queue_id": queue["id"],
            "subject_type": "artifact",
            "subject_id": str(subject),
            "content_hash": _digest("artifact", subject),
            "statement_text": "I reviewed it.",
        },
    )
    with pytest.raises(ConflictError):
        reviews.delete_queue(admin, uuid.UUID(str(queue["id"])))
    store.blobs[subject] = b"changed"
    with pytest.raises(ConflictError):
        reviews.decide(
            admin,
            uuid.UUID(str(opened["id"])),
            {
                "decision": "approve",
                "content_hash": opened["content_hash"],
                "statement_hash": opened["statement_hash"],
            },
            stepped_up=True,
        )
    fresh = reviews.open_item(
        builder,
        {
            "queue_id": queue["id"],
            "subject_type": "artifact",
            "subject_id": str(subject),
            "content_hash": hashlib.sha256(b"changed").hexdigest(),
            "statement_text": "I reviewed the change.",
        },
    )
    outsider = Actor(
        demo_id("tenant"),
        demo_id("member"),
        frozenset({"reviews:read"}),
        roles=frozenset({"member"}),
    )
    assert reviews.list_items(outsider, scope="all", status="pending", queue_id=None)
    with pytest.raises(ForbiddenError):
        reviews.list_items(
            Actor(demo_id("tenant"), demo_id("member"), frozenset(), roles=frozenset()),
            scope="all",
            status=None,
            queue_id=None,
        )
    assert reviews.list_items(builder, scope="prepared", status=None, queue_id=queue["id"])
    with pytest.raises(ForbiddenError):
        reviews.decide(
            builder,
            uuid.UUID(str(fresh["id"])),
            {
                "decision": "approve",
                "content_hash": fresh["content_hash"],
                "statement_hash": fresh["statement_hash"],
            },
            stepped_up=True,
        )
    step_queue = reviews.create_queue(
        admin,
        {
            "slug": "step",
            "name": "Step",
            "subject_type": "evidence_item",
            "levels": [{"level": 1, "step_up": True}],
        },
    )
    evidence = uuid.uuid4()
    stepped_item = reviews.open_item(
        builder,
        {
            "queue_id": step_queue["id"],
            "subject_id": str(evidence),
            "content_hash": _digest("evidence_item", evidence),
            "statement_text": "Evidence.",
        },
    )
    approver = Actor(
        demo_id("tenant"),
        demo_id("approver"),
        PERMISSION_KEYS,
        roles=frozenset({"approver", "tenant_admin"}),
        auth_method="api_key",
    )
    with pytest.raises(StepUpRequiredError):
        reviews.decide(
            approver,
            uuid.UUID(str(stepped_item["id"])),
            {
                "decision": "approve",
                "content_hash": stepped_item["content_hash"],
                "statement_hash": stepped_item["statement_hash"],
            },
            stepped_up=True,
        )
    session = Actor(
        demo_id("tenant"),
        demo_id("approver"),
        PERMISSION_KEYS,
        roles=frozenset({"approver", "tenant_admin"}),
        auth_method="session",
    )
    with pytest.raises(StepUpRequiredError):
        reviews.decide(
            session,
            uuid.UUID(str(stepped_item["id"])),
            {
                "decision": "reject",
                "content_hash": stepped_item["content_hash"],
                "statement_hash": stepped_item["statement_hash"],
            },
            stepped_up=False,
        )
    first = reviews.decide(
        session,
        uuid.UUID(str(fresh["id"])),
        {
            "decision": "approve",
            "content_hash": fresh["content_hash"],
            "statement_hash": fresh["statement_hash"],
            "comment": "level one",
        },
        stepped_up=True,
    )
    assert first["status"] == "in_review"
    second_user = Actor(
        demo_id("tenant"),
        demo_id("checker"),
        PERMISSION_KEYS,
        roles=frozenset({"tenant_admin"}),
    )
    signed = reviews.decide(
        second_user,
        uuid.UUID(str(fresh["id"])),
        {
            "decision": "approve",
            "content_hash": fresh["content_hash"],
            "statement_hash": fresh["statement_hash"],
        },
        stepped_up=True,
    )
    assert signed["status"] == "signed"
    assert reviews.get_item(admin, uuid.UUID(str(fresh["id"])))["signoffs"]

    message_id = new_id()
    store.messages[message_id] = {"id": message_id, "text": "hello", "run_id": None}
    message_queue = reviews.create_queue(
        admin,
        {
            "slug": "messages",
            "name": "Messages",
            "subject_type": "message",
            "levels": [{"level": 1}],
        },
    )
    digest = hashlib.sha256(b"hello").hexdigest()
    message_item = reviews.open_item(
        builder,
        {
            "queue_id": message_queue["id"],
            "subject_id": str(message_id),
            "content_hash": digest,
            "statement_text": "Read.",
        },
    )
    with pytest.raises(NotFoundError):
        reviews.open_item(
            builder,
            {
                "queue_id": message_queue["id"],
                "subject_id": str(uuid.uuid4()),
                "content_hash": "0" * 64,
                "statement_text": "Missing.",
            },
        )
    pack_id = uuid.uuid4()
    pack_queue = reviews.create_queue(
        admin,
        {
            "slug": "packs",
            "name": "Packs",
            "subject_type": "pack_record",
            "levels": [{"level": 1, "role_key": "ghost"}],
        },
    )
    reviews.open_item(
        builder,
        {
            "queue_id": pack_queue["id"],
            "subject_id": str(pack_id),
            "subject_ref": {"content_hash": "abc"},
            "content_hash": "abc",
            "statement_text": "Pack.",
        },
    )
    delegate_queue = reviews.create_queue(
        admin,
        {
            "slug": "delegate",
            "name": "Delegate",
            "subject_type": "binder",
            "levels": [{"level": 1}],
        },
    )
    binder = uuid.uuid4()
    delegated = reviews.open_item(
        builder,
        {
            "queue_id": delegate_queue["id"],
            "subject_id": str(binder),
            "content_hash": _digest("binder", binder),
            "statement_text": "Bind.",
        },
    )
    target = demo_id("checker")
    store.user_roles[target] = {"tenant_admin"}
    moved = reviews.decide(
        admin,
        uuid.UUID(str(delegated["id"])),
        {
            "decision": "delegate",
            "delegated_to_user_id": str(target),
            "content_hash": delegated["content_hash"],
            "statement_hash": delegated["statement_hash"],
            "comment": "over to you",
        },
        stepped_up=True,
    )
    assert moved["status"] == "pending"
    with pytest.raises(ValidationFailedError):
        reviews.decide(
            admin,
            uuid.UUID(str(message_item["id"])),
            {
                "decision": "delegate",
                "delegated_to_user_id": str(demo_id("member")),
                "content_hash": message_item["content_hash"],
                "statement_hash": message_item["statement_hash"],
            },
            stepped_up=True,
        )
    with pytest.raises(ValidationFailedError):
        reviews.decide(
            admin,
            uuid.UUID(str(message_item["id"])),
            {
                "decision": "shrug",
                "content_hash": message_item["content_hash"],
                "statement_hash": message_item["statement_hash"],
            },
            stepped_up=True,
        )
    rejected = reviews.decide(
        admin,
        uuid.UUID(str(message_item["id"])),
        {
            "decision": "reject",
            "content_hash": message_item["content_hash"],
            "statement_hash": message_item["statement_hash"],
            "comment": "no",
        },
        stepped_up=True,
    )
    assert rejected["status"] == "rejected"
    with pytest.raises(ValidationFailedError):
        reviews.bulk(admin, {"decision": "reject", "items": [{}] * 101}, stepped_up=True)
    with pytest.raises(NotFoundError):
        reviews.get_item(admin, uuid.uuid4())
    hidden = Actor(demo_id("tenant"), uuid.uuid4(), frozenset(), roles=frozenset())
    with pytest.raises(NotFoundError):
        reviews.get_item(hidden, uuid.UUID(str(rejected["id"])))

    sod = SodBook(store)
    with pytest.raises(ValidationFailedError):
        sod.create_constraint(admin, {"role_a": "author", "role_b": "author", "applies_to": "both"})
    with pytest.raises(ValidationFailedError):
        sod.create_constraint(
            admin, {"role_a": "author", "role_b": "checker", "applies_to": "nope"}
        )
    created = sod.create_constraint(
        admin, {"role_a": "author", "role_b": "checker", "applies_to": "both"}
    )
    patched_rule = sod.patch_constraint(
        admin, uuid.UUID(str(created["id"])), {"enabled": False, "applies_to": "signoff"}
    )
    assert patched_rule["enabled"] is False
    sod.patch_constraint(
        admin, uuid.UUID(str(created["id"])), {"enabled": True, "applies_to": "both"}
    )
    assert sod.get_constraint(admin, uuid.UUID(str(created["id"])))["role_a"] == "author"
    store.user_roles[admin.user_id] = {"author"}
    store.user_roles[builder.user_id] = {"checker"}
    author = Actor(
        demo_id("tenant"),
        admin.user_id,
        PERMISSION_KEYS,
        roles=frozenset({"author", "tenant_admin"}),
    )
    with pytest.raises(ValidationFailedError):
        sod.assert_approval(
            author,
            {"id": new_id(), "requested_for_user_id": builder.user_id, "four_eyes": False},
            decision="reject",
        )
    agent_id = new_id()
    store.agents[agent_id] = {"id": agent_id, "owner_user_id": author.user_id}
    blocked = sod.approval_violations(
        author,
        {
            "agent_id": agent_id,
            "requested_for_user_id": author.user_id,
            "four_eyes": True,
        },
    )
    assert blocked
    routine = new_id()
    store.routines[routine] = {"owner_user_id": author.user_id}
    with pytest.raises(ValidationFailedError):
        sod.assert_standing(author, routine)
    sod.assert_standing(author, None)
    item = {
        "id": new_id(),
        "preparer_principal_id": builder.user_id,
        "subject_type": "message",
        "subject_id": message_id,
        "agent_id": agent_id,
    }
    store.signoffs[new_id()] = {
        "review_item_id": item["id"],
        "decision": "approve",
        "signer_principal_id": author.user_id,
        "level": 1,
    }
    assert sod.signoff_violations(author, item)
    checked = sod.check(
        admin,
        {
            "action": "approval",
            "signer_principal_id": str(author.user_id),
            "preparer_principal_id": str(builder.user_id),
            "agent_id": str(agent_id),
        },
    )
    assert checked["violations"]
    simulated = sod.simulate(
        author, {"agent_id": str(agent_id), "user_id": str(builder.user_id)}, {}
    )
    assert simulated["violations"]
    assert sod.simulate(author, {}, {})["allowed"] is True


def test_policy_book_and_gateway_wrappers() -> None:
    store = ChatService()
    actor = Actor(
        demo_id("tenant"),
        demo_id("admin"),
        PERMISSION_KEYS,
        roles=frozenset({"tenant_admin"}),
        auth_method="session",
    )
    book = PolicyBook(store)
    document = {
        "rules": [
            {
                "id": "allow-read",
                "effect": "allow",
                "match": {"tools": ["petstore.get_pet"]},
            }
        ],
        "tests": [
            {
                "name": "read is allowed",
                "input": {"tool": {"qualified_name": "petstore.get_pet", "risk_class": "R0"}},
                "expect": {"decision": "allow"},
            },
            "skip",
        ],
    }
    created = book.create(actor, {"name": "Desk", "description": "reads", "document": document})
    assert book.list_policies(actor)
    assert book.get(actor, uuid.UUID(str(created["id"])))["name"] == "Desk"
    with pytest.raises(ConflictError):
        book.create(actor, {"name": "Desk", "document": document})
    with pytest.raises(ConflictError):
        book.create(actor, {"name": " ", "document": document})
    with pytest.raises(ValidationFailedError):
        book.create(actor, {"name": "Other", "kind": "prose", "document": document})
    with pytest.raises(ValidationFailedError):
        book.create(
            actor,
            {"name": "Custom", "kind": "rego", "rego": "package ar.custom\ndeny { true }"},
        )
    store.tenant_settings[actor.tenant_id] = {"features": {"custom_rego": True}}
    custom = book.create(
        actor,
        {
            "name": "Custom",
            "kind": "rego",
            "rego": 'package ar.custom\ndeny { input.tool.risk_class == "W3" }',
        },
    )
    with pytest.raises(ValidationFailedError):
        book.add_version(actor, uuid.UUID(str(custom["id"])), {"rego": "package ar.custom\n"})
    renamed = book.patch(
        actor,
        uuid.UUID(str(created["id"])),
        {"name": "Desk rules", "description": "", "priority": 10},
    )
    assert renamed["name"] == "Desk rules"
    other = book.create(
        actor,
        {"name": "Taken", "document": {"rules": [{"id": "x", "effect": "deny", "match": {}}]}},
    )
    with pytest.raises(ConflictError):
        book.patch(actor, uuid.UUID(str(created["id"])), {"name": "Taken"})
    failing = {
        "rules": [{"id": "deny-all", "effect": "deny", "match": {}}],
        "tests": [
            {
                "name": "expects allow",
                "input": {"tool": {"qualifiedName": "petstore.get_pet", "riskClass": "R0"}},
                "expect": {"decision": "allow", "ruleIds": ["missing"]},
            }
        ],
    }
    version = book.add_version(actor, uuid.UUID(str(created["id"])), {"document": failing})
    assert version["test_report"]["passed"] is False
    with pytest.raises(StepUpRequiredError):
        book.activate(actor, uuid.UUID(str(created["id"])), 1, stepped_up=False)
    with pytest.raises(ValidationFailedError):
        book.activate(
            actor, uuid.UUID(str(created["id"])), int(version["version"]), stepped_up=True
        )
    with pytest.raises(NotFoundError):
        book.activate(actor, uuid.UUID(str(created["id"])), 99, stepped_up=True)
    activated = book.activate(actor, uuid.UUID(str(created["id"])), 1, stepped_up=True)
    assert activated["status"] == "active"
    assert book.versions(actor, uuid.UUID(str(created["id"])))
    with pytest.raises(ConflictError):
        book.delete(actor, uuid.UUID(str(created["id"])))
    disabled = book.disable(actor, uuid.UUID(str(created["id"])))
    assert disabled["status"] == "disabled"
    book.delete(actor, uuid.UUID(str(other["id"])))
    with pytest.raises(NotFoundError):
        book.get(actor, uuid.uuid4())
    draft = book.create(
        actor,
        {
            "name": "Draft only",
            "document": {"rules": [{"id": "d", "effect": "allow", "match": {}}]},
        },
    )
    simulated = book.simulate(
        actor,
        {
            "tool_qualified_name": "petstore.get_pet",
            "args": {"id": 1},
            "include_drafts": ["not-a-uuid", str(draft["id"]), str(uuid.uuid4())],
            "agent_id": str(uuid.uuid4()),
        },
    )
    assert "decision" in simulated
    call_id = new_id()
    store.tool_calls[call_id] = {
        "id": call_id,
        "tenant_id": actor.tenant_id,
        "qualified_name": "petstore.get_pet",
        "arguments_redacted": {"id": 1},
    }
    book.simulate(actor, {"tool_call_id": str(call_id)})
    with pytest.raises(NotFoundError):
        book.simulate(actor, {"tool_call_id": "nope"})
    with pytest.raises(ValidationFailedError):
        book.add_version(
            actor,
            uuid.UUID(str(draft["id"])),
            {"document": {"rules": [{"id": f"r{i}", "effect": "deny"} for i in range(201)]}},
        )
    for index in range(98):
        store.policies[new_id()] = {"tenant_id": actor.tenant_id, "name": f"pad-{index}"}
    with pytest.raises(ValidationFailedError):
        book.create(actor, {"name": "Overflow", "document": {"rules": []}})

    version_row = next(iter(store.tool_versions.values()))
    tool = store.tool_defs[uuid.UUID(str(version_row["tool_id"]))]
    server_version = store.tool_server_versions[
        uuid.UUID(str(version_row["tool_server_version_id"]))
    ]
    server = store.tool_servers[uuid.UUID(str(server_version["tool_server_id"]))]
    decision = gateway_decide(
        store,
        {
            "tenant_id": actor.tenant_id,
            "user_id": actor.user_id,
            "arguments": {},
            "run_id": None,
            "agent_id": None,
        },
        version_row,
        tool,
        server,
    )
    assert decision["decision"]
    assert isinstance(gateway_book(store), ApprovalBook)
