"""An assistant reply is labelled as not reviewed until a named person accepts it."""

import hashlib
import uuid
from dataclasses import replace

from fastapi.testclient import TestClient

from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.db.context import Principal
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_application

_LEVELS = [{"level": 1, "name": "Reviewer", "role_key": "", "required_count": 1}]


def _client(
    permissions: frozenset[str] | None = None,
    *,
    user: str = "admin",
    tenant: uuid.UUID | None = None,
    stepped: bool = False,
) -> tuple[TestClient, list[Principal]]:
    app = demo_application()
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


def _become(
    holder: list[Principal],
    user: str,
    *,
    stepped: bool = False,
    permissions: frozenset[str] | None = None,
    tenant: uuid.UUID | None = None,
) -> None:
    holder[0] = replace(
        holder[0],
        id=str(demo_id(user)),
        email=f"{user}@dev.local",
        display_name=user,
        roles=frozenset({"tenant_admin"}) if user == "admin" else frozenset(),
        step_up_at=utcnow() if stepped else None,
        permissions=permissions if permissions is not None else PERMISSION_KEYS,
        tenant_id=tenant or demo_id("tenant"),
    )


def _queue(client: TestClient, *, subject: str = "message", slug: str = "replies") -> str:
    made = client.post(
        "/api/v1/review-queues",
        json={
            "slug": slug,
            "name": "Reply acceptance",
            "subjectType": subject,
            "levels": _LEVELS,
            "statementTemplate": "I reviewed the reply in {title} ({content_hash}).",
        },
    )
    assert made.status_code == 200, made.text
    return str(made.json()["id"])


def _set_up(client: TestClient) -> str:
    """The admin makes a queue for messages and names it for reply acceptance."""
    queue_id = _queue(client)
    saved = client.patch(
        "/api/v1/tenant", json={"settings": {"approvals": {"replyReviewQueueId": queue_id}}}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["approvals"]["replyReviewQueueId"] == queue_id
    return queue_id


def _ask(client: TestClient, text: str = "What can you do?") -> tuple[str, dict[str, object]]:
    """Ask the assistant in a new conversation. Returns the conversation and its reply."""
    conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
    posted = client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"text": text})
    assert posted.status_code == 202, posted.text
    return conversation_id, _replies(client, conversation_id)[-1]


def _replies(client: TestClient, conversation_id: str) -> list[dict[str, object]]:
    body = client.get(f"/api/v1/conversations/{conversation_id}").json()
    return [row for row in body["messages"] if row["role"] == "assistant"]


def _actions(client: TestClient) -> list[str]:
    return [str(row["action"]) for row in client.app.state.chat.audit_log]


def test_a_reply_is_unreviewed_and_cannot_be_accepted_until_a_queue_is_chosen() -> None:
    client, holder = _client()
    _become(holder, "approver", stepped=True)
    _conversation, reply = _ask(client)
    assert reply["status"] == "completed"
    assert reply["review"] == {
        "status": "unreviewed",
        "acceptedBy": None,
        "acceptedAt": None,
        "contentHash": hashlib.sha256(str(reply["text"]).encode()).hexdigest(),
        "reviewItemId": None,
        "canAccept": False,
    }
    refused = client.post(f"/api/v1/messages/{reply['id']}:accept")
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "invalid_state"
    assert "approvals.replyReviewQueueId" in refused.json()["detail"]
    assert "review_item.created" not in _actions(client)


def test_the_person_who_asked_accepts_and_the_signer_time_and_hash_are_recorded() -> None:
    client, holder = _client()
    queue_id = _set_up(client)
    _become(holder, "approver")
    conversation_id, reply = _ask(client)
    assert reply["review"]["status"] == "unreviewed"
    assert reply["review"]["canAccept"] is True
    store = client.app.state.chat
    before = len(store.review_items)

    early = client.post(f"/api/v1/messages/{reply['id']}:accept")
    assert early.status_code == 403, early.text
    assert early.json()["stepUpRequired"] is True
    assert len(store.review_items) == before, "a refused acceptance leaves no open item"

    _become(holder, "approver", stepped=True)
    accepted = client.post(f"/api/v1/messages/{reply['id']}:accept", json={"comment": "Checked"})
    assert accepted.status_code == 200, accepted.text
    review = accepted.json()
    digest = hashlib.sha256(str(reply["text"]).encode()).hexdigest()
    assert review["status"] == "accepted"
    assert review["acceptedBy"]["id"] == str(demo_id("approver"))
    assert review["acceptedBy"]["name"]
    assert review["acceptedAt"]
    assert review["contentHash"] == digest
    assert review["canAccept"] is False

    item = store.review_items[uuid.UUID(review["reviewItemId"])]
    assert item["status"] == "signed"
    assert str(item["queue_id"]) == queue_id
    assert item["content_hash"] == digest
    assert item["preparer_principal_type"] == "agent"
    assert item["preparer_principal_id"] == item["agent_id"]
    assert digest in str(item["statement_text"])
    signoffs = [row for row in store.signoffs.values() if row["review_item_id"] == item["id"]]
    assert len(signoffs) == 1
    assert signoffs[0]["signer_principal_id"] == demo_id("approver")
    assert signoffs[0]["content_hash"] == digest
    assert signoffs[0]["step_up_at"] is not None
    tail = _actions(client)[-3:]
    assert tail == ["review_item.created", "signoff.recorded", "review_item.decided"]

    shown = _replies(client, conversation_id)[-1]["review"]
    assert shown == review

    again = client.post(f"/api/v1/messages/{reply['id']}:accept")
    assert again.status_code == 200, again.text
    assert again.json() == review
    assert len([row for row in store.signoffs.values() if row["review_item_id"] == item["id"]]) == 1
    assert _actions(client)[-3:] == tail


def test_the_owner_of_the_agent_cannot_accept_its_reply() -> None:
    client, holder = _client(stepped=True)
    _set_up(client)
    _conversation, reply = _ask(client)
    assert reply["review"]["canAccept"] is False
    store = client.app.state.chat
    before = len(store.review_items)
    blocked = client.post(f"/api/v1/messages/{reply['id']}:accept")
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["detail"] == "sod_violation"
    assert len(store.review_items) == before
    assert _actions(client)[-1] == "sod.violation_blocked"
    _become(holder, "approver", stepped=True)
    assert client.post(f"/api/v1/messages/{reply['id']}:accept").status_code == 200


def test_acceptance_does_not_carry_to_a_regenerated_or_changed_reply() -> None:
    client, holder = _client()
    _set_up(client)
    _become(holder, "approver", stepped=True)
    conversation_id, reply = _ask(client)
    assert client.post(f"/api/v1/messages/{reply['id']}:accept").status_code == 200

    again = client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{reply['id']}:regenerate"
    )
    assert again.status_code == 202, again.text
    replies = _replies(client, conversation_id)
    by_id = {row["id"]: row for row in replies}
    assert len(by_id) == 2
    assert by_id[reply["id"]]["review"]["status"] == "accepted"
    fresh = next(row for row in replies if row["id"] != reply["id"])
    assert fresh["review"]["status"] == "unreviewed"
    assert fresh["review"]["acceptedBy"] is None
    if fresh["status"] != "completed":
        # A reply that is still being written is labelled, and cannot be accepted yet.
        assert fresh["review"]["canAccept"] is False
        early = client.post(f"/api/v1/messages/{fresh['id']}:accept")
        assert early.status_code == 409, early.text
        assert early.json()["code"] == "invalid_state"
        stored_fresh = client.app.state.chat.messages[uuid.UUID(str(fresh["id"]))]
        stored_fresh["text"] = "A second answer."
        stored_fresh["status"] = "completed"
        fresh = next(row for row in _replies(client, conversation_id) if row["id"] == fresh["id"])
    assert fresh["review"]["canAccept"] is True

    # The acceptance is of the exact text: when the text differs, it no longer applies.
    stored = client.app.state.chat.messages[uuid.UUID(str(reply["id"]))]
    stored["text"] = f"{stored['text']} (changed)"
    changed = next(row for row in _replies(client, conversation_id) if row["id"] == reply["id"])
    assert changed["review"]["status"] == "unreviewed"
    assert changed["review"]["acceptedAt"] is None


def test_accept_is_hidden_from_another_tenant_and_refused_without_the_permission() -> None:
    client, holder = _client()
    _set_up(client)
    _become(holder, "approver", stepped=True)
    _conversation, reply = _ask(client)
    path = f"/api/v1/messages/{reply['id']}:accept"

    _become(holder, "approver", stepped=True, tenant=uuid.uuid4())
    assert client.post(path).status_code == 404

    _become(holder, "approver", stepped=True, permissions=frozenset({"chat:use"}))
    assert client.post(path).status_code == 403

    # Someone who cannot read the conversation cannot learn the reply exists.
    _become(holder, "member", stepped=True, permissions=frozenset({"chat:use", "reviews:decide"}))
    assert client.post(path).status_code == 404
    assert client.post(f"/api/v1/messages/{uuid.uuid4()}:accept").status_code == 404

    _become(holder, "approver", stepped=True, permissions=frozenset({"chat:use"}))
    shown = client.get(f"/api/v1/conversations/{_conversation}").json()["messages"][-1]
    assert shown["review"]["canAccept"] is False
    assert "signoff.recorded" not in _actions(client)


def test_only_a_reply_can_be_accepted() -> None:
    client, holder = _client()
    _set_up(client)
    _become(holder, "approver", stepped=True)
    conversation_id, _reply = _ask(client)
    body = client.get(f"/api/v1/conversations/{conversation_id}").json()
    question = next(row for row in body["messages"] if row["role"] == "user")
    assert "review" not in question
    refused = client.post(f"/api/v1/messages/{question['id']}:accept")
    assert refused.status_code == 422, refused.text


def test_the_setting_names_a_message_queue_of_this_tenant() -> None:
    client, _holder = _client()
    unknown = client.patch(
        "/api/v1/tenant",
        json={"settings": {"approvals": {"replyReviewQueueId": str(uuid.uuid4())}}},
    )
    assert unknown.status_code == 422, unknown.text
    wrong = _queue(client, subject="file", slug="files")
    refused = client.patch(
        "/api/v1/tenant", json={"settings": {"approvals": {"replyReviewQueueId": wrong}}}
    )
    assert refused.status_code == 422, refused.text
    assert "message" in refused.json()["detail"]

    queue_id = _set_up(client)
    in_use = client.delete(f"/api/v1/review-queues/{queue_id}")
    assert in_use.status_code == 409, in_use.text
    cleared = client.patch(
        "/api/v1/tenant", json={"settings": {"approvals": {"replyReviewQueueId": None}}}
    )
    assert cleared.status_code == 200, cleared.text
    assert client.delete(f"/api/v1/review-queues/{queue_id}").status_code == 200
