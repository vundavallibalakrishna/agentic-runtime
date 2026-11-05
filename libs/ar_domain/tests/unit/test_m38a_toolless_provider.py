"""An agent with no tools is answered by the tenant's own provider. Task: M38a-T02f."""

import uuid
from typing import TYPE_CHECKING

import pytest

from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS

if TYPE_CHECKING:
    from ar_testing.stand_in import StandIn

SCRIPT_SET = "m38a-t02f"


@pytest.mark.asyncio
async def test_a_tool_less_agent_reaches_the_registered_provider(stand_in: StandIn) -> None:
    tenant, user = demo_id("tenant"), demo_id("admin")
    store = ChatService(allow_loopback=True)
    stand_in.script(SCRIPT_SET, [{"match": {"contains": "capital"}, "respond": {"text": "Paris."}}])
    stand_in.connect(store, tenant, script_set=SCRIPT_SET)
    actor = Actor(tenant_id=tenant, user_id=user, permissions=PERMISSION_KEYS, display_name="A")
    life = AgentLifecycle(store)
    created = life.create(actor, slug="plain", name="Plain", description="no tools")
    agent_id = uuid.UUID(str(created["id"]))
    life.publish(actor, agent_id, change_note="first")
    version = store.versions[store.agents[agent_id]["published_version_id"]]
    assert not version["definition"].get("tools"), "the agent under test has no tools"

    conversation = store.create_conversation(tenant, user, agent_id)
    question = "What is the capital of France?"
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), question, schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await store.generate(run_id, question, [])

    run = store.runs[run_id]
    assert run["status"] == "completed"
    assert store.messages[run["assistant_message_id"]]["text"] == "Paris."
