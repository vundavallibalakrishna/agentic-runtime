"""Policy, approval, review and segregation HTTP surface."""

import uuid
from dataclasses import replace

from fastapi.testclient import TestClient

from ar_api.main import create_application
from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS


def _client(
    permissions: frozenset[str] | None = None,
    *,
    user: str = "admin",
    tenant: uuid.UUID | None = None,
    stepped: bool = False,
) -> tuple[TestClient, list[Principal]]:
    app = create_application()
    principal = Principal(
        kind="user",
        id=str(demo_id(user)),
        tenant_id=tenant or demo_id("tenant"),
        permissions=permissions if permissions is not None else PERMISSION_KEYS,
        team_permissions=frozenset(),
        auth_method="bearer",
        email=f"{user}@dev.local",
        display_name=user,
        roles=frozenset({"tenant_admin"}) if user == "admin" else frozenset(),
        step_up_at=utcnow() if stepped else None,
    )

    holder = [principal]

    async def resolve(scope: object) -> Principal:
        del scope
        return holder[0]

    app.state.resolve_principal = resolve
    app.state.await_runs = True
    return TestClient(app), holder


def _become(holder: list[Principal], user: str, *, stepped: bool) -> None:
    holder[0] = replace(
        holder[0],
        id=str(demo_id(user)),
        email=f"{user}@dev.local",
        display_name=user,
        step_up_at=utcnow() if stepped else None,
    )


def _document(effect: str = "deny", *, decision: str = "deny") -> dict[str, object]:
    return {
        "rules": [
            {
                "id": "pets",
                "effect": effect,
                "message": "no pets",
                "match": {"tools": ["petstore.create_pet"]},
            }
        ],
        "tests": [
            {
                "name": "pets",
                "input": {"tool": {"qualifiedName": "petstore.create_pet", "riskClass": "W2"}},
                "expect": {"decision": decision},
            }
        ],
    }


def test_policy_lifecycle_simulation_and_bundle() -> None:
    client, _principal = _client()
    created = client.post(
        "/api/v1/policies",
        json={"name": "No pets", "description": "Block creating pets", "document": _document()},
    )
    assert created.status_code == 200, created.text
    policy_id = created.json()["id"]
    hidden = _client(tenant=uuid.uuid4())[0].get(f"/api/v1/policies/{policy_id}")
    assert hidden.status_code == 404
    reader = _client(permissions=frozenset({"policies:read"}))[0]
    assert (
        reader.post("/api/v1/policies", json={"name": "x", "document": _document()}).status_code
        == 403
    )
    patched = client.patch(f"/api/v1/policies/{policy_id}", json={"description": "Still no pets"})
    assert patched.status_code == 200
    versions = client.get(f"/api/v1/policies/{policy_id}/versions")
    assert versions.json()["items"]
    activated = client.post(f"/api/v1/policies/{policy_id}:activate", json={"version": 1})
    assert activated.status_code == 200, activated.text
    live = client.post(
        "/api/v1/policies:simulate",
        json={"toolQualifiedName": "petstore.create_pet", "args": {"body": {"name": "Fido"}}},
    )
    assert live.status_code == 200, live.text
    assert live.json()["decision"] == "deny"
    draft = client.post(
        "/api/v1/policies",
        json={
            "name": "Draft only",
            "document": _document("allow", decision="allow"),
        },
    )
    assert draft.status_code == 200, draft.text
    unchanged = client.post(
        "/api/v1/policies:simulate",
        json={"toolQualifiedName": "petstore.create_pet"},
    )
    assert unchanged.json()["decision"] == "deny"
    drafted = client.post(
        "/api/v1/policies:simulate",
        json={
            "toolQualifiedName": "petstore.create_pet",
            "includeDrafts": [draft.json()["id"]],
        },
    )
    assert drafted.json()["decision"] == "deny"
    assert "sod" in drafted.json()
    broken = client.post(
        "/api/v1/policies",
        json={"name": "Broken", "document": _document("deny", decision="allow")},
    )
    assert broken.status_code == 200
    blocked = client.post(f"/api/v1/policies/{broken.json()['id']}:activate", json={"version": 1})
    assert blocked.status_code == 422
    disabled = client.post(f"/api/v1/policies/{policy_id}:disable")
    assert disabled.status_code == 200
    after = client.post(
        "/api/v1/policies:simulate",
        json={"toolQualifiedName": "petstore.create_pet"},
    )
    assert after.json()["decision"] == "require_approval"
    isolated = client.post(
        "/api/v1/policies:simulate",
        json={
            "toolQualifiedName": "petstore.create_pet",
            "includeDrafts": [draft.json()["id"]],
        },
    )
    assert isolated.json()["decision"] == "allow"
    deleted = client.delete(f"/api/v1/policies/{policy_id}")
    assert deleted.status_code == 200
    bundle = client.get("/internal/v1/opa/bundles/ar.tar.gz")
    assert bundle.status_code == 200
    etag = bundle.headers["etag"]
    cached = client.get("/internal/v1/opa/bundles/ar.tar.gz", headers={"if-none-match": etag})
    assert cached.status_code == 304
    audit = client.get("/api/v1/audit-events")
    assert audit.status_code == 200
    actions = {item["action"] for item in audit.json()["items"]}
    assert "policy.created" in actions


def test_pet_waits_for_approval_then_runs_once() -> None:
    client, holder = _client()
    agents = client.get("/api/v1/agents").json()["items"]
    desk = next(item for item in agents if item["slug"] == "desk")
    conversation = client.post("/api/v1/conversations", json={"agentId": desk["id"]})
    assert conversation.status_code in {200, 201}, conversation.text
    conversation_id = conversation.json()["id"]
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": "Create a pet named Fido"},
    )
    assert posted.status_code == 202, posted.text
    body = client.get(f"/api/v1/conversations/{conversation_id}").json()
    texts = " ".join(str(item.get("text") or "") for item in body["messages"])
    assert "Waiting for approval" in texts
    inbox = client.get("/api/v1/approvals", params={"scope": "to_decide"}).json()["items"]
    assert inbox
    approval_id = inbox[0]["id"]
    detail = client.get(f"/api/v1/approvals/{approval_id}").json()
    other = _client(tenant=uuid.uuid4())[0].get(f"/api/v1/approvals/{approval_id}")
    assert other.status_code == 404
    changed = client.post(
        f"/api/v1/approvals/{approval_id}:decide",
        json={"decision": "approve", "argsHash": "not-the-hash"},
    )
    assert changed.status_code == 409
    decided = client.post(
        f"/api/v1/approvals/{approval_id}:decide",
        json={"decision": "approve", "argsHash": detail["argsHash"], "comment": "Go ahead"},
    )
    assert decided.status_code == 200, decided.text
    finished = client.get(f"/api/v1/conversations/{conversation_id}").json()
    done = " ".join(str(item.get("text") or "") for item in finished["messages"])
    assert "Created pet" in done
    again = client.post(
        f"/api/v1/approvals/{approval_id}:decide",
        json={"decision": "approve", "argsHash": detail["argsHash"]},
    )
    assert again.status_code in {403, 409}
    assert holder[0].email == "admin@dev.local"


def test_w3_requires_step_up_and_reviews_sign_off() -> None:
    client, holder = _client()
    approver_id = str(demo_id("approver"))
    policy = client.post(
        "/api/v1/policies",
        json={
            "name": "Deletes wait",
            "document": {
                "rules": [
                    {
                        "id": "del",
                        "effect": "requireApproval",
                        "message": "confirm the delete",
                        "match": {"tools": ["petstore.delete_pet"]},
                        "approval": {"approvers": {"mode": "users", "users": [approver_id]}},
                    }
                ]
            },
        },
    )
    assert policy.status_code == 200, policy.text
    activated = client.post(f"/api/v1/policies/{policy.json()['id']}:activate", json={"version": 1})
    assert activated.status_code == 200, activated.text
    agents = client.get("/api/v1/agents").json()["items"]
    desk = next(item for item in agents if item["slug"] == "desk")
    conversation = client.post("/api/v1/conversations", json={"agentId": desk["id"]})
    conversation_id = conversation.json()["id"]
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": "Delete pet 1"},
    )
    assert posted.status_code == 202, posted.text
    own = client.get("/api/v1/approvals", params={"riskClass": "W3"}).json()["items"]
    assert own == []
    requested = client.get(
        "/api/v1/approvals", params={"scope": "requested", "riskClass": "W3"}
    ).json()["items"]
    assert requested
    approval_id = requested[0]["id"]
    detail = client.get(f"/api/v1/approvals/{approval_id}").json()
    assert detail["stepUpRequired"] is True
    assert detail["fourEyes"] is True
    self_approve = client.post(
        f"/api/v1/approvals/{approval_id}:decide",
        json={"decision": "approve", "argsHash": detail["argsHash"]},
    )
    assert self_approve.status_code == 403
    _become(holder, "approver", stepped=False)
    inbox = client.get("/api/v1/approvals", params={"riskClass": "W3"}).json()["items"]
    assert inbox
    blocked = client.post(
        f"/api/v1/approvals/{approval_id}:decide",
        json={"decision": "approve", "argsHash": detail["argsHash"]},
    )
    assert blocked.status_code == 403
    assert blocked.json()["stepUpRequired"] is True
    _become(holder, "approver", stepped=True)
    approved = client.post(
        f"/api/v1/approvals/{approval_id}:decide",
        json={"decision": "approve", "argsHash": detail["argsHash"], "comment": "Confirmed"},
    )
    assert approved.status_code == 200, approved.text
    _become(holder, "admin", stepped=False)
    finished = client.get(f"/api/v1/conversations/{conversation_id}").json()
    done = " ".join(str(item.get("text") or "") for item in finished["messages"])
    assert "Deleted pet" in done
    queues = client.get("/api/v1/review-queues").json()["items"]
    assert any(item["name"] == "Output review" for item in queues)
    items = client.get("/api/v1/review-items").json()["items"]
    assert items
    item_id = items[0]["id"]
    review = client.get(f"/api/v1/review-items/{item_id}").json()
    _become(holder, "admin", stepped=False)
    early = client.post(
        f"/api/v1/review-items/{item_id}:decide",
        json={
            "decision": "approve",
            "contentHash": review["contentHash"],
            "statementHash": review["statementHash"],
        },
    )
    assert early.status_code == 403
    _become(holder, "admin", stepped=True)
    signed = client.post(
        f"/api/v1/review-items/{item_id}:decide",
        json={
            "decision": "approve",
            "comment": "Looks right",
            "contentHash": review["contentHash"],
            "statementHash": review["statementHash"],
        },
    )
    assert signed.status_code == 200, signed.text
    mismatch = client.post(
        "/api/v1/review-items",
        json={
            "queueId": queues[0]["id"],
            "subjectType": "artifact",
            "subjectId": str(uuid.uuid4()),
            "contentHash": "nope",
            "statementText": "I reviewed it.",
        },
    )
    assert mismatch.status_code == 422
    constraints = client.get("/api/v1/sod-constraints")
    assert constraints.status_code == 200
    created = client.post(
        "/api/v1/sod-constraints",
        json={"roleA": "author", "roleB": "approver", "appliesTo": "both"},
    )
    assert created.status_code == 200, created.text
    hidden = _client(tenant=uuid.uuid4())[0].get(f"/api/v1/sod-constraints/{created.json()['id']}")
    assert hidden.status_code == 404


def test_input_on_a_completed_run_stays_conflict() -> None:
    client, _principal = _client()
    conversation = client.post("/api/v1/conversations", json={})
    conversation_id = conversation.json()["id"]
    posted = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"text": "Hello"},
    )
    run_id = posted.json()["run"]["id"]
    empty = client.post(f"/api/v1/runs/{run_id}:input")
    assert empty.status_code == 409
