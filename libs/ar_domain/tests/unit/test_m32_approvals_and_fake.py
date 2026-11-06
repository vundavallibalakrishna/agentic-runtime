"""Approvals do not deadlock on SoD; fake models do not echo outside dev. Tasks M32-T03/T04."""

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from ar_domain.approvals.logic import can_decide, is_approver, requester_blocked
from ar_domain.approvals.service import ApprovalBook
from ar_domain.tools.agent_loop import run_agent_loop
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService


def _actor(user_id: uuid.UUID, *perms: str) -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id, tenant_id=uuid.uuid4(), permissions=frozenset(perms))


def _approval(store: ChatService, requester: uuid.UUID, *, owner: uuid.UUID) -> dict[str, object]:
    agent_id = uuid.uuid4()
    store.agents[agent_id] = {"id": agent_id, "owner_user_id": owner}
    return {
        "id": uuid.uuid4(),
        "status": "pending",
        "agent_id": agent_id,
        "requested_for_user_id": requester,
        "approver_rule": {"mode": "requester"},
        "four_eyes": False,
    }


def test_requester_mode_lets_another_approver_decide_when_sod_blocks_the_requester() -> None:
    store = demo_store()
    requester, approver, bystander = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    blocked = _approval(store, requester, owner=requester)
    assert requester_blocked(store, blocked) is True
    assert is_approver(store, _actor(requester), blocked) is True, "SoD is enforced at decide"
    assert can_decide(store, _actor(approver, "approvals:decide"), blocked) is True
    assert can_decide(store, _actor(bystander), blocked) is False
    free = _approval(store, requester, owner=uuid.uuid4())
    assert requester_blocked(store, free) is False
    assert can_decide(store, _actor(approver, "approvals:decide"), free) is False
    assert can_decide(store, _actor(requester), free) is True
    four_eyes = dict(free, four_eyes=True)
    assert requester_blocked(store, four_eyes) is True
    assert can_decide(store, _actor(approver, "approvals:decide"), four_eyes) is True


def test_blocked_requester_notifies_role_holders_who_can_decide() -> None:
    store = demo_store()
    requester, approver, member = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    store.user_roles[requester] = {"tenant_admin"}
    store.user_roles[approver] = {"approver"}
    store.user_roles[member] = {"member"}
    row = _approval(store, requester, owner=requester)
    ids = ApprovalBook(store)._approver_ids(row)
    assert str(approver) in ids
    assert str(member) not in ids
    assert str(requester) not in ids
    free = _approval(store, requester, owner=uuid.uuid4())
    assert ApprovalBook(store)._approver_ids(free) == [str(requester)]


@pytest.mark.asyncio
async def test_fake_alias_fails_the_run_when_fake_models_are_not_allowed() -> None:
    store = demo_store()
    store.fake_models_allowed = False
    tenant_id = next(iter(store.agents.values()))["tenant_id"]
    agent = next(row for row in store.agents.values() if row.get("slug") == "assistant")
    version = store.versions[agent["published_version_id"]]
    run_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    store.conversations[conversation_id] = {"id": conversation_id, "active_run_id": run_id}
    run: dict[str, object] = {
        "id": run_id,
        "tenant_id": tenant_id,
        "agent_id": agent["id"],
        "agent_version_id": version["id"],
        "user_id": uuid.uuid4(),
        "conversation_id": conversation_id,
        "status": "running",
    }
    store.runs[run_id] = run
    store.events[run_id] = []
    assistant: dict[str, object] = {"id": uuid.uuid4(), "status": "streaming"}
    handled = await run_agent_loop(store, run, assistant, "hello")
    assert handled is True
    assert run["status"] == "failed"
    assert run["error"]["code"] == "model_unavailable"
    assert "fake:" not in str(assistant.get("text"))
    store.fake_models_allowed = True
    run["status"] = "running"
    assert await run_agent_loop(store, run, assistant, "hello") is False
