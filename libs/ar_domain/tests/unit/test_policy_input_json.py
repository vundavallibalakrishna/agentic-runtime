"""The question sent to the policy engine is JSON, for every kind of run."""

from __future__ import annotations

import uuid

import httpx

from ar_domain.demo_ids import demo_id
from ar_domain.policy.engine import _input
from ar_testing.demo import demo_store


def test_a_routine_runs_tool_call_can_be_sent_to_the_policy_engine() -> None:
    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Run now", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    routine_id = uuid.uuid4()
    run["trigger"] = "routine"
    run["routine_id"] = routine_id
    request = {"tenant_id": tenant, "run_id": run["id"], "arguments": {"skill": "notes"}}
    built = _input(store, request, {"qualified_name": "skills.load"}, {"slug": "skills"}, {})
    assert built["run"] == {
        "id": str(run["id"]),
        "trigger": "routine",
        "channel": "web",
        "depth": 0,
        "routine_id": str(routine_id),
    }
    # The policy sidecar is asked over HTTP: the whole input has to encode as JSON.
    sent = httpx.Request("POST", "http://opa.invalid/v1/data", json={"input": built})
    assert str(routine_id).encode() in sent.content


def test_a_chat_run_names_no_routine() -> None:
    store = demo_store()
    built = _input(store, {"tenant_id": demo_id("tenant")}, {}, {}, {})
    assert built["run"]["routine_id"] is None  # type: ignore[index]
