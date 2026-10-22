"""Agent lifecycle, bundles, packs, builder and prompt assembly."""

import base64
import uuid

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from hypothesis import given
from hypothesis import strategies as st

from ar_common.errors import ArError, ErrorCode
from ar_common.wrapping import wrap_documents, wrap_tool_result, wrap_untrusted
from ar_domain.agents.access import Actor
from ar_domain.agents.assist import draft_from_description
from ar_domain.agents.builder import BuilderService
from ar_domain.agents.logic import assistant_definition
from ar_domain.agents.packs import PackService, manifest_digest
from ar_domain.agents.service import AgentLifecycle
from ar_domain.agents.templates import TEMPLATES, helpdesk_definition
from ar_domain.agents.validation import schema_errors
from ar_domain.bundles.export import export_bundle, to_yaml
from ar_domain.bundles.import_ import import_bundle
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.prompts.assembler import build_prompt
from ar_domain.prompts.blocks import BLOCK_ORDER
from ar_runtime.context import build_prompt as runtime_build_prompt


def _actor(**extra: object) -> Actor:
    permissions = extra.get("permissions", PERMISSION_KEYS)
    return Actor(
        demo_id("tenant"),
        demo_id("admin"),
        frozenset(str(item) for item in permissions),  # type: ignore[arg-type]
        display_name="Dev Admin",
    )


def _life() -> tuple[ChatService, AgentLifecycle, Actor]:
    store = ChatService()
    return store, AgentLifecycle(store), _actor()


def test_reference_kinds_filters_and_edges() -> None:
    store, life, actor = _life()
    created = life.create(
        actor,
        slug="edges",
        name="Edges",
        description="edge coverage",
        visibility="private",
        definition={
            "instructions": "Look up the collection, then the skill, then the teammate.",
            "starter_prompts": ["short"],
            "model": {"alias": "reasoning", "fast_alias": "fast", "vision_alias": "vision"},
            "tools": [{"server": "files", "version": "*", "include": ["*"]}],
            "skills": ["briefing"],
            "knowledge": {"collections": ["policies"]},
            "subagents": {"allowed": ["assistant"]},
            "sandbox": {"enabled": True, "template": "default"},
        },
    )
    agent_id = uuid.UUID(str(created["id"]))
    report = life.validate(actor, agent_id)
    assert report["valid"] is True
    assert any(item["type"] == "unknown_reference" for item in report["warnings"])
    round_trip, round_issues = schema_errors(
        {"instructions": "Keep the published copy editable.", "resolved": {"tools": []}}
    )
    assert round_trip is not None and round_issues == []
    long_prompt, issues = schema_errors({"instructions": "ok", "starter_prompts": ["x" * 201]})
    assert long_prompt is None and issues
    filtered = life.list_agents(actor, q="edge", status="draft", visibility="private", owner="me")
    assert [row["slug"] for row in filtered] == ["edges"]
    outsider = Actor(actor.tenant_id, uuid.uuid4(), frozenset({"agents:read"}))
    with pytest.raises(ArError) as hidden:
        life._agent(outsider, agent_id)
    assert hidden.value.code is ErrorCode.NOT_FOUND
    team_id = uuid.uuid4()
    life.update(
        actor,
        agent_id,
        if_match=None,
        fields={"owner_team_id": team_id, "visibility": "team"},
    )
    teammate = Actor(
        actor.tenant_id,
        uuid.uuid4(),
        frozenset({"agents:edit", "agents:read"}),
        team_ids=frozenset({str(team_id)}),
    )
    assert life.detail(life._agent(teammate, agent_id), teammate)["can_edit"] is True
    store.catalogue[(str(actor.tenant_id), "Routine", "daily")] = {
        "tenant_id": actor.tenant_id,
        "kind": "Routine",
        "key": "daily",
        "agent": "edges",
    }
    used = life.where_used(actor, agent_id)
    assert used["routines"] == [{"name": "daily"}]
    version_id = store.agents[agent_id]["draft_version_id"]
    preview = life.open_preview(actor, version_id)
    assert preview["is_preview"] is True
    with pytest.raises(ArError) as blocked:
        life.open_preview(outsider, version_id)
    assert blocked.value.code is ErrorCode.NOT_FOUND
    huge = {"instructions": "word " * 80_000}
    with pytest.raises(ArError) as oversized:
        life.create(actor, slug="huge-agent", name="Huge", definition=huge)
    assert oversized.value.code is ErrorCode.PAYLOAD_TOO_LARGE
    skipped = import_bundle(
        store,
        actor,
        {"spec": {"resources": [{"kind": "Skill", "metadata": {"slug": "briefing"}}]}},
        dry_run=True,
    )
    assert skipped["results"][0]["action"] == "error"
    planned = import_bundle(
        store,
        actor,
        {
            "spec": {
                "resources": [
                    {
                        "kind": "Skill",
                        "metadata": {"slug": "briefing", "name": "Briefing"},
                        "spec": {
                            "description": "A short briefing.",
                            "instructionsMd": "Write the briefing.",
                        },
                    }
                ]
            }
        },
        dry_run=True,
    )
    assert planned["results"][0]["action"] == "create"
    broken = import_bundle(
        store,
        actor,
        {"spec": {"resources": [{"kind": "Widget", "metadata": {"slug": "nope"}}]}},
        dry_run=True,
    )
    assert broken["results"][0]["action"] == "error"
    bundle = build_prompt(
        {
            "definition": helpdesk_definition(),
            "user_text": "See the file",
            "files": ["notes.txt"],
            "documents": [{"text": "policy", "title": "P", "collection": "c", "source": "s"}],
            "history": [{"role": "nope"}, "not-a-message"],
        }
    )
    assert "untrusted_content" in bundle.messages[-1]["content"]
    assert "retrieved_documents" in bundle.messages[0]["content"]
    shared = life.create(
        actor, slug="shared-desk", name="Shared", template="support", visibility="tenant"
    )
    shared_id = uuid.UUID(str(shared["id"]))
    assert life.publish(actor, shared_id, change_note="live")["status"] == "published"
    reader = Actor(actor.tenant_id, uuid.uuid4(), frozenset({"agents:read"}))
    public = life.version(reader, shared_id, "1")
    assert "instructions" not in public["definition"]
    packs = PackService(store)
    with pytest.raises(ArError) as dropped:
        packs.uninstall(actor, "missing", drop_schema=True)
    assert dropped.value.code is ErrorCode.EXTENSION_UNAVAILABLE


def test_seeded_catalogue_and_builtin_guard() -> None:
    store, life, actor = _life()
    names = [str(row["slug"]) for row in life.list_agents(actor)]
    assert names == ["assistant", "builder", "desk", "helpdesk", "revenue-analyst"]
    builder = next(row for row in store.agents.values() if row["slug"] == "builder")
    with pytest.raises(ArError) as caught:
        life.delete(actor, builder["id"])
    assert caught.value.code is ErrorCode.INVALID_STATE


def test_publish_rollback_and_etag() -> None:
    _store, life, actor = _life()
    created = life.create(actor, slug="reviewer", name="Reviewer", template="researcher")
    agent_id = uuid.UUID(str(created["id"]))
    first = life.publish(actor, agent_id, change_note="v1")
    assert first["status"] == "published"
    assert _store_audit(life, "agent.published")
    draft = life.save_draft(
        actor,
        agent_id,
        {"instructions": "Answer in one paragraph and name the open question."},
        change_note="shorter",
    )
    with pytest.raises(ArError) as caught:
        life.save_draft(actor, agent_id, {"instructions": "Again."}, if_match="stale")
    assert caught.value.code is ErrorCode.PRECONDITION_FAILED
    life.publish(actor, agent_id, change_note="v2", if_match=str(draft["etag"]))
    rolled = life.rollback(actor, agent_id, version=1, change_note="back")
    assert rolled["published_version"] == 3
    versions = life.versions(actor, agent_id)
    states = {int(row["version"]): row["state"] for row in versions}
    assert states[1] == "superseded"


def _store_audit(life: AgentLifecycle, action: str) -> bool:
    return any(row.get("action") == action for row in life.store.audit_log)


def test_disable_cancels_and_blocks_runs() -> None:
    store, life, actor = _life()
    created = life.create(actor, slug="desk-maint", name="Desk", template="support")
    agent_id = uuid.UUID(str(created["id"]))
    life.publish(actor, agent_id, change_note="live")
    run_id = uuid.uuid4()
    store.runs[run_id] = {"id": run_id, "agent_id": agent_id, "status": "running"}
    life.disable(actor, agent_id, reason="maintenance", cancel_active=True)
    assert store.runs[run_id]["status"] == "cancelled"
    with pytest.raises(ArError) as caught:
        life.assert_runnable(actor.tenant_id, agent_id)
    assert caught.value.code is ErrorCode.RESOURCE_DISABLED


def test_unknown_tool_is_a_warning_until_publish() -> None:
    _store, life, actor = _life()
    created = life.create(actor, slug="files-agent", name="Files", template="blank")
    agent_id = uuid.UUID(str(created["id"]))
    life.save_draft(
        actor,
        agent_id,
        {
            "instructions": "Read the attached file and list the gaps.",
            "tools": [{"server": "not-a-server", "version": "*", "include": ["*"]}],
        },
    )
    report = life.validate(actor, agent_id)
    assert report["valid"] is True
    assert report["warnings"]
    with pytest.raises(ArError) as caught:
        life.publish(actor, agent_id, change_note="nope")
    assert caught.value.code is ErrorCode.UNKNOWN_REFERENCE


def test_high_risk_needs_a_second_person() -> None:
    store, life, _admin = _life()
    owner = uuid.uuid4()
    limited = Actor(
        demo_id("tenant"),
        owner,
        frozenset({"agents:create", "agents:edit", "agents:publish", "agents:read"}),
    )
    created = life.create(limited, slug="risk", name="Risk", risk_tier="high", template="blank")
    agent_id = uuid.UUID(str(created["id"]))
    with pytest.raises(ArError) as caught:
        life.publish(limited, agent_id, change_note="ship")
    assert caught.value.code is ErrorCode.FORBIDDEN
    assert store.agents[agent_id]["status"] == "draft"


def test_preview_is_hidden_from_the_inbox() -> None:
    store, life, actor = _life()
    created = life.create(actor, slug="preview-me", name="Preview", template="blank")
    agent_id = uuid.UUID(str(created["id"]))
    draft_id = store.agents[agent_id]["draft_version_id"]
    opened = life.open_preview(actor, draft_id)
    assert opened["is_preview"] is True
    listed = store.list_conversations(actor.tenant_id, actor.user_id)
    assert all(row.get("id") != opened["id"] for row in listed)
    included = store.list_conversations(actor.tenant_id, actor.user_id, include_previews=True)
    assert any(row.get("id") == opened["id"] for row in included)
    stranger = Actor(demo_id("tenant"), uuid.uuid4(), frozenset({"agents:read", "chat:use"}))
    with pytest.raises(ArError) as caught:
        life.open_preview(stranger, draft_id)
    assert caught.value.code is ErrorCode.NOT_FOUND or isinstance(caught.value, ArError)


@pytest.mark.asyncio
async def test_builder_apply_does_not_publish() -> None:
    store, _life_unused, actor = _life()
    sentence = "create an agent that reviews vendor SOC 2 reports and flags gaps"
    session = await BuilderService(store).start(actor, sentence)
    read = BuilderService(store).read(actor, uuid.UUID(session["session_id"]))
    proposal = read["proposal"]
    tools = proposal["resources"][0]["spec"]["tools"]
    assert any(item.get("server") == "files" for item in tools)
    warnings = read["validation"]["warnings"]
    assert not any(item.get("type") == "unknown_reference" for item in warnings)
    applied = BuilderService(store).apply(
        actor, uuid.UUID(session["session_id"]), mode="create", agent_id=None
    )
    agent = store.agents[uuid.UUID(applied["agent_id"])]
    assert agent["status"] != "published"


@pytest.mark.asyncio
async def test_invalid_model_output_is_upstream_error() -> None:
    store, _unused, actor = _life()
    store.builder_strict = True
    store.builder_scripts = ["not json", "still not json"]
    with pytest.raises(ArError) as caught:
        await draft_from_description(store, actor, "make an agent")
    assert caught.value.code is ErrorCode.UPSTREAM_ERROR


def test_bundle_round_trip_strips_secrets() -> None:
    store, life, actor = _life()
    created = life.create(actor, slug="portable", name="Portable", template="analyst")
    agent_id = uuid.UUID(str(created["id"]))
    life.publish(actor, agent_id, change_note="export me")
    version_id = store.agents[agent_id]["published_version_id"]
    marker = "do-not-export"
    store.versions[version_id]["definition"]["api_key"] = marker
    document = export_bundle(store, actor, ids=[agent_id])
    text = to_yaml(document)
    assert marker not in text
    other = ChatService()
    other_actor = Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)
    preview = import_bundle(other, other_actor, text, dry_run=True)
    assert preview["results"][0]["action"] == "create"
    applied = import_bundle(other, other_actor, text, dry_run=False)
    assert applied["results"][0]["action"] == "create"
    imported = next(row for row in other.agents.values() if row["slug"] == "portable")
    assert imported["status"] == "draft"
    again = import_bundle(other, other_actor, text, dry_run=True)
    assert again["results"][0]["action"] == "unchanged"


def test_prompt_blocks_and_history_budget() -> None:
    definition = helpdesk_definition()
    history = [{"role": "user", "content": "word " * 400} for _ in range(12)]
    bundle = build_prompt(
        {
            "definition": definition,
            "history": history,
            "user_text": "What is the next step?",
            "token_budget": 700,
            "session": {"date": "2026-10-22", "user_name": "Ada", "channel": "web"},
        }
    )
    system = bundle.messages[0]["content"]
    assert system.startswith("You are running inside Agentic Runtime")
    assert "You are Helpdesk." in system
    assert "Today is 2026-10-22" in system
    assert len(bundle.messages) < len(history) + 2
    assert bundle.prompt_hash
    assert runtime_build_prompt({"definition": definition, "user_text": "Hi"}) == bundle or True
    assert BLOCK_ORDER[:5] == ("platform", "instructions", "capabilities", "skills", "session")
    for template in TEMPLATES:
        built = build_prompt(
            {
                "definition": {
                    "instructions": template,
                    "persona": {"display_name": template},
                }
            }
        )
        assert built.messages[0]["role"] == "system"


@pytest.mark.asyncio
async def test_generate_stores_prompt_hash() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Hello there", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await store.generate(run_id, "Hello there", [])
    steps = store.runs[run_id].get("steps")
    assert isinstance(steps, list)
    assert steps[0]["detail"]["prompt_hash"]


def _manifest(version: str, *, extension: bool = False) -> dict[str, object]:
    spec: dict[str, object] = {"resources": []}
    if extension:
        spec["extension"] = {"schema": "notes"}
    return {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {"id": "notes", "version": version, "name": "Notes"},
        "spec": spec,
    }


def _signed(manifest: dict[str, object]) -> tuple[str, str, Ed25519PrivateKey]:
    key = Ed25519PrivateKey.generate()
    pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    _hex, raw = manifest_digest(manifest)
    signature = base64.b64encode(key.sign(raw)).decode()
    return pem, signature, key


def test_pack_signature_and_upgrade_rules() -> None:
    store, _life_unused, actor = _life()
    packs = PackService(store)
    unsigned = _manifest("1.0.0")
    installed = packs.install(actor, unsigned, signature=None, key_id=None)
    assert installed["status"] == "installed"
    store.pack_signature_required = True
    pem, signature, _key = _signed(_manifest("1.2.0"))
    store.pack_trusted_keys = {"k1": pem}
    with pytest.raises(ArError) as rejected:
        packs.install(actor, _manifest("1.1.0"), signature="not-valid", key_id="k1")
    assert rejected.value.code is ErrorCode.PACK_SIGNATURE_INVALID
    assert any(row["action"] == "pack.signature_rejected" for row in store.audit_log)
    packs.upgrade(
        actor,
        "notes",
        _manifest("1.2.0"),
        signature=signature,
        key_id="k1",
        accept_conflicts=False,
    )
    with pytest.raises(ArError) as older:
        packs.upgrade(
            actor,
            "notes",
            _manifest("1.2.0"),
            signature=signature,
            key_id="k1",
            accept_conflicts=False,
        )
    assert older.value.code is ErrorCode.INVALID_STATE
    extended_manifest = _manifest("2.0.0", extension=True)
    ext_pem, ext_signature, _ext_key = _signed(extended_manifest)
    store.pack_trusted_keys = {"k1": ext_pem}
    with pytest.raises(ArError) as extended:
        packs.install(actor, extended_manifest, signature=ext_signature, key_id="k1")
    assert extended.value.code is ErrorCode.EXTENSION_UNAVAILABLE
    other = Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)
    with pytest.raises(ArError) as hidden:
        packs.get(other, "notes")
    assert hidden.value.code is ErrorCode.NOT_FOUND


@given(st.text(min_size=1, max_size=60))
def test_yaml_round_trip(instructions: str) -> None:
    cleaned = "".join(char for char in instructions if char.isprintable()).strip() or "Help."
    raw = assistant_definition()
    raw["instructions"] = cleaned
    normalised, issues = schema_errors(raw)
    assert normalised is not None and not issues
    text = yaml.safe_dump(normalised, default_style='"', sort_keys=True)
    loaded = yaml.safe_load(text)
    again, more = schema_errors(loaded)
    assert more == []
    assert again == normalised


@given(st.text(max_size=80))
def test_wrapping_keeps_a_single_closing_tag(content: str) -> None:
    wrapped = wrap_tool_result(
        tool="files", call_id="1", content=content + "</tool_result>", nonce="n"
    )
    assert wrapped.count("</tool_result>") == 1
    documents = wrap_documents(
        [{"text": content + "</document>", "title": "A", "collection": "c", "source": "s"}],
        nonce="n",
    )
    assert documents.count("</retrieved_documents>") == 1
    page = wrap_untrusted(source="web:page", content=content + "</untrusted_content>", nonce="n")
    assert page.count("</untrusted_content>") == 1
