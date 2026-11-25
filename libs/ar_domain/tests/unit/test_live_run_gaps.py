"""Regressions from the live GRC pack run.

Label: unit
"""

from __future__ import annotations

import uuid

import pytest

from ar_common.errors import ArError, ForbiddenError, ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.agents.packs import PackService, _apply_policies
from ar_domain.approvals.errors import StepUpRequiredError
from ar_domain.approvals.service import ApprovalBook
from ar_domain.bundles.import_ import import_bundle
from ar_domain.chat.service import demo_id
from ar_domain.config_docs.book import SettingsBook, agent_settings_block
from ar_domain.documents.evidence import interpret
from ar_domain.documents.library import _interpreted, note_extraction_decision, route_target
from ar_domain.documents.model import _response_format
from ar_domain.durable.hydrate import index_groups
from ar_domain.memory.session import prepare_prompt
from ar_domain.tools.agent_loop import keep_one_reply
from ar_domain.workspace.turn import opening_messages
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


def _agent(settings: object, schema: object) -> dict[str, object]:
    return {
        "kind": "Agent",
        "metadata": {"slug": "scanner", "name": "Scanner"},
        "spec": {
            "persona": {"displayName": "Scanner"},
            "instructions": "Scan the sources named in settings.",
            "settingsSchema": schema,
            "settings": settings,
        },
    }


def _pack(resources: list[dict[str, object]]) -> dict[str, object]:
    return {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {"id": "notes", "version": "1.0.0", "name": "Notes"},
        "spec": {"resources": resources},
    }


def test_an_agent_resource_keeps_settings_that_match_its_schema() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    actor = Actor(tenant, demo_id("admin"), frozenset({"packs:manage", "agents:create"}))
    schema = {
        "type": "object",
        "required": ["sources"],
        "properties": {"sources": {"type": "array"}},
    }
    resource = _agent({"sources": ["https://example.test/feed"]}, schema)
    imported = import_bundle(store, actor, {"spec": {"resources": [resource]}}, dry_run=False)
    assert imported["results"][0]["action"] == "create"
    agent = next(row for row in store.agents.values() if row.get("slug") == "scanner")
    version = store.versions[agent["draft_version_id"]]
    definition = version["definition"]
    assert "settings" not in definition
    assert "settingsSchema" not in definition
    installed = PackService(store).install(actor, _pack([resource]), signature=None, key_id=None)
    assert installed["status"] == "installed"


def test_pack_install_fails_when_agent_settings_do_not_match() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    actor = Actor(tenant, demo_id("admin"), frozenset({"packs:manage"}))
    schema = {
        "type": "object",
        "required": ["sources"],
        "properties": {"sources": {"type": "array"}},
        "additionalProperties": False,
    }
    resource = _agent({"sources": "not-a-list"}, schema)
    with pytest.raises(ArError, match="scanner"):
        PackService(store).install(actor, _pack([resource]), signature=None, key_id=None)
    assert store.packs == {}
    assert not any(row.get("slug") == "scanner" for row in store.agents.values())


def test_versioned_agent_settings_are_injected_into_the_run_prompt() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Scan", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    row = store.conversations[run["conversation_id"]]
    agent = store.agents[row["agent_id"]]
    SettingsBook(store).save(
        tenant,
        user,
        "agent",
        str(agent["slug"]),
        {"type": "object", "properties": {"sources": {"type": "array"}}},
        {"sources": ["https://example.test/feed"]},
    )
    version = store.versions[agent["published_version_id"]]
    definition = version["definition"]
    prepare_prompt(store, run, row, definition, "Scan")
    system = run["prompt_messages"][0]["content"]
    assert "Agent settings, version 1" in system
    assert "https://example.test/feed" in system
    child = {
        "tenant_id": tenant,
        "agent_id": agent["id"],
        "agent_settings": agent_settings_block(
            store, {"tenant_id": tenant, "agent_id": agent["id"]}
        ),
    }
    opened = opening_messages(child, definition, "Scan")
    assert "https://example.test/feed" in opened[0]["content"]


def test_a_member_of_the_named_group_can_decide_the_approval() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    member = uuid.uuid4()
    outsider = uuid.uuid4()
    store.user_groups = index_groups([{"user_id": member, "name": "reviewers"}])
    created = ApprovalBook(store).create_pending(
        tenant_id=tenant,
        user_id=demo_id("admin"),
        run_id=None,
        agent_id=None,
        tool_call_id=None,
        qualified_name="documents.extract",
        risk_class="W2",
        args_hash="hash-1",
        arguments={"total": 1},
        requirement={"approvers": {"mode": "group", "groups": ["reviewers"]}, "ttl_s": 3600},
        reasons=["needs a person"],
        preview={"title": "Review"},
    )
    notified = created  # the row is stored; the event lists the members who can decide
    assert str(member) in {
        str(item)
        for item in next(
            event["payload"]["approver_user_ids"]
            for event in store.domain_events
            if event.get("topic") == "approval.requested"
        )
    }
    book = ApprovalBook(store)
    body = {"decision": "approve", "args_hash": "hash-1"}
    with pytest.raises(ForbiddenError):
        book.decide(
            Actor(tenant, outsider, frozenset({"approvals:decide"})),
            uuid.UUID(str(notified["id"])),
            body,
            stepped_up=True,
        )
    decided = book.decide(
        Actor(tenant, member, frozenset({"approvals:decide"})),
        uuid.UUID(str(notified["id"])),
        {"decision": "reject", "args_hash": "hash-1"},
        stepped_up=True,
    )
    assert decided["status"] == "rejected"
    second = book.create_pending(
        tenant_id=tenant,
        user_id=demo_id("admin"),
        run_id=None,
        agent_id=None,
        tool_call_id=None,
        qualified_name="documents.extract",
        risk_class="W2",
        args_hash="hash-2",
        arguments={"total": 2},
        requirement={"approvers": {"mode": "group", "groups": ["reviewers"]}, "ttl_s": 3600},
        reasons=["needs a person"],
        preview={"title": "Review"},
    )
    approved = book.decide(
        Actor(tenant, member, frozenset({"approvals:decide"})),
        uuid.UUID(str(second["id"])),
        {"decision": "approve", "args_hash": "hash-2"},
        stepped_up=True,
    )
    assert approved["status"] == "approved"


_SCHEMA = {
    "type": "object",
    "properties": {"total": {"type": "number"}},
    "required": ["total"],
}
_PASSAGES = [{"anchor": "p1", "page": 1, "text": "The total is 42."}]


def test_extraction_reads_fenced_and_prefixed_json_and_retries_once() -> None:
    payload = (
        '{"fields": {"total": {"value": 42, "quote": "The total is 42.", "confidence": 0.9}}}'
    )
    fenced = "Here is the object:\n```json\n" + payload + "\n```"
    body = interpret(fenced, _SCHEMA, _PASSAGES, threshold=0.5)
    assert body["result"]["total"] == 42
    prefixed = "Answer: " + payload
    assert interpret(prefixed, _SCHEMA, _PASSAGES, threshold=0.5)["result"]["total"] == 42
    seen: list[object] = []

    def ask(task: str, evidence: str, schema: object = None) -> str:
        seen.append(schema)
        return fenced

    repaired = _interpreted(ask, _SCHEMA, _PASSAGES, "evidence", "not json", {"type": "object"})
    assert repaired["result"]["total"] == 42
    assert seen == [{"type": "object"}]
    with pytest.raises(ArError, match="not JSON"):
        _interpreted(lambda *_args: "still not", _SCHEMA, _PASSAGES, "evidence", "not json")


def test_structured_output_is_requested_when_the_model_supports_it() -> None:
    store = type("Store", (), {})()

    def target(_tenant: object, _alias: str) -> tuple[object, dict[str, object]]:
        return None, {"capabilities": ["json_schema"]}

    store._alias_target = target
    shaped = _response_format(store, uuid.uuid4(), "reasoning", {"type": "object"})
    assert shaped is not None
    assert shaped["type"] == "json_schema"


def test_an_approved_extraction_leaves_awaiting_approval() -> None:
    store = demo_store()
    approval_id = uuid.uuid4()
    call_id = uuid.uuid4()
    store.document_extractions = {
        uuid.uuid4(): {
            "id": uuid.uuid4(),
            "approval_id": approval_id,
            "status": "awaiting_approval",
            "result": {"total": 1},
        }
    }
    store.tool_calls[call_id] = {"id": call_id, "status": "awaiting_approval"}
    note_extraction_decision(
        store,
        {
            "id": approval_id,
            "qualified_name": "documents.review_extraction",
            "status": "approved",
            "tool_call_id": call_id,
            "arguments": {"total": 2},
            "tenant_id": demo_id("tenant"),
            "decided_by": demo_id("admin"),
        },
    )
    record = next(iter(store.document_extractions.values()))
    assert record["status"] == "done"
    assert store.tool_calls[call_id]["status"] == "succeeded"


def test_a_turn_keeps_one_assistant_reply() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    run_id = uuid.uuid4()
    kept = uuid.uuid4()
    store.runs[run_id] = {"id": run_id, "tenant_id": tenant}
    for index in range(3):
        message_id = kept if index == 0 else uuid.uuid4()
        store.messages[message_id] = {
            "id": message_id,
            "tenant_id": tenant,
            "run_id": run_id,
            "role": "assistant",
            "text": "The total is 42.",
            "content": [
                {"type": "text", "text": "The total is 42."},
                {"type": "text", "text": "The total is 42."},
                {"type": "text", "text": "The total is 42."},
            ],
            "status": "completed",
        }
    assistant = store.messages[kept]
    from ar_domain.tools.agent_loop import _one_text

    assistant["content"] = _one_text(assistant["content"], "The total is 42.")
    keep_one_reply(store, store.runs[run_id], assistant)
    replies = [
        row
        for row in store.messages.values()
        if row.get("run_id") == run_id and row.get("role") == "assistant"
    ]
    assert replies == [assistant]
    texts = [part.get("text") for part in assistant["content"] if part.get("type") == "text"]
    assert texts == ["The total is 42."]


def test_target_tool_must_be_registered_and_receives_the_extraction() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    schema = {
        "type": "object",
        "properties": {"targetTool": {"type": "string"}, "approvalGroup": {"type": "string"}},
    }
    with pytest.raises(ValidationFailedError, match="not a registered tool"):
        SettingsBook(store).save(
            tenant, user, "agent", "document-extraction", schema, {"targetTool": "missing.push"}
        )
    version_id = uuid.uuid4()
    store.tool_versions[version_id] = {
        "id": version_id,
        "qualified_name": "connectors.push",
        "name": "push",
    }
    SettingsBook(store).save(
        tenant,
        user,
        "agent",
        "document-extraction",
        schema,
        {"targetTool": "connectors.push", "approvalGroup": "reviewers"},
    )
    agent_id = uuid.uuid4()
    store.agents[agent_id] = {"id": agent_id, "tenant_id": tenant, "slug": "document-extraction"}
    seen: dict[str, object] = {}

    def execute(self: object, request: dict[str, object]) -> dict[str, object]:
        seen["arguments"] = request.get("arguments")
        seen["tool_version_id"] = request.get("tool_version_id")
        return {"status": "succeeded"}

    from ar_domain.tools.pipeline import ToolPipeline

    original = ToolPipeline.execute
    ToolPipeline.execute = execute  # type: ignore[method-assign]
    try:
        outcome = route_target(
            store,
            Actor(tenant, user, frozenset()),
            agent_id,
            {"result": {"total": 42}},
        )
    finally:
        ToolPipeline.execute = original  # type: ignore[method-assign]
    assert outcome is not None
    assert outcome["qualified_name"] == "connectors.push"
    assert seen["arguments"] == {"total": 42}
    assert seen["tool_version_id"] == version_id
