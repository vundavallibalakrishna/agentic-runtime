"""GRC pack catalogues, crosswalks, evidence links, tools and entities."""

import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from ar_common.errors import ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.packs.registry import permissions_for, register_pack_permissions
from ar_domain.records.memory import bucket
from ar_domain.records.vault import EvidenceBook
from ar_domain.tools.pipeline import ToolPipeline
from ar_pack_grc.entities import create_entity, posture, scope_to_entity, set_parent
from ar_pack_grc.evidence_links import create_link, delete_link, list_links
from ar_pack_grc.frameworks import get_framework, import_oscal, import_statements, patch_framework
from ar_pack_grc.install import catalogue_bytes, install_for
from ar_pack_grc.mappings import confirm_mapping, create_mapping, reject_mapping, suggest
from ar_pack_grc.mcp_server import put_answer, put_policy, put_vendor
from ar_pack_grc.models import PackBase
from ar_pack_grc.oscal import export_catalog

PERMS = PERMISSION_KEYS | frozenset(
    {
        "grc.frameworks:read",
        "grc.frameworks:manage",
        "grc.controls:read",
        "grc.controls:manage",
        "grc.evidence:link",
        "grc.entities:read",
        "grc.entities:manage",
        "evidence:read",
        "evidence:capture",
    }
)


def _actor(**extra: object) -> Actor:
    tenant = extra.get("tenant_id", demo_id("tenant"))
    user = extra.get("user_id", demo_id("admin"))
    permissions = extra.get("permissions", PERMS)
    return Actor(
        tenant_id=tenant,  # type: ignore[arg-type]
        user_id=user,  # type: ignore[arg-type]
        permissions=permissions,  # type: ignore[arg-type]
        kind=str(extra.get("kind", "user")),
        roles=frozenset({"tenant_admin"}),
    )


def _installed() -> tuple[ChatService, Actor]:
    store = ChatService()
    actor = _actor()
    install_for(store, actor)
    return store, actor


def _upload(store: ChatService, actor: Actor, name: str, data: bytes) -> uuid.UUID:
    uploaded = store.upload(actor.tenant_id, actor.user_id, name, "text/plain", data)
    return uuid.UUID(str(uploaded["id"]))


def test_pack_models_cover_the_domain_and_the_entity_tree() -> None:
    names = {
        table.name for table in PackBase.metadata.tables.values() if table.schema == "grc"
    }
    assert "regulator_feeds" in names
    assert "entities" in names
    assert len(names) == 28
    assert "entity_id" in PackBase.metadata.tables["grc.controls"].c


def test_import_linter_still_forbids_the_pack() -> None:
    text = Path(".importlinter").read_text(encoding="utf-8")
    assert "ar_pack_grc" in text
    assert "packs-not-in-core" in text


def test_oscal_round_trip_and_licence_refusal() -> None:
    store, actor = _installed()
    file_id = _upload(store, actor, "csf.json", catalogue_bytes("nist-csf-2.0.json"))
    imported = import_oscal(store, actor, file_id)
    framework_id = uuid.UUID(imported["framework_id"])
    exported = export_catalog(store, actor, framework_id, include_mappings=True)
    prose = str(exported)
    assert "Access to assets is limited" in prose
    skeleton = next(
        row for row in store.records["grc_frameworks"].values() if row["key"] == "iso-27001"
    )
    bare = export_catalog(store, actor, skeleton["id"], include_mappings=False)
    assert "prose" not in str(bare["catalog"])
    refused = False
    try:
        import_statements(store, actor, framework_id, file_id, attestation=True)
    except ValidationFailedError as exc:
        refused = exc.detail == "licence=free"
    assert refused
    csv_id = _upload(
        store, actor, "licensed.csv", b"key,statement\na.5.15,Licensed access text\nnope,no\n"
    )
    with pytest.raises(ValidationFailedError):
        import_statements(store, actor, skeleton["id"], csv_id, attestation=False)
    with pytest.raises(ValidationFailedError, match="nope"):
        import_statements(store, actor, skeleton["id"], csv_id, attestation=True)
    good = _upload(store, actor, "ok.csv", b"key,statement\na.5.15,Licensed access text\n")
    filled = import_statements(store, actor, skeleton["id"], good, attestation=True)
    assert filled["updated"] == 1
    actions = [row["action"] for row in store.audit_log]
    assert "grc.framework.imported" in actions
    attested = [row for row in store.audit_log if row["detail"].get("licence_attested") is True]
    assert attested
    with pytest.raises(ForbiddenError, match="pack_owned"):
        patch_framework(store, actor, framework_id, {"name": "Renamed"})


def test_two_person_confirm_and_reject() -> None:
    store, actor = _installed()
    other = _actor(user_id=demo_id("builder"))
    controls = [row for row in store.records["grc_controls"].values() if row["framework_id"]]
    created = create_mapping(
        store,
        actor,
        {
            "from_control_id": str(controls[0]["id"]),
            "to_control_id": str(controls[1]["id"]),
            "confidence": 0.4,
            "rationale": "possible",
        },
    )
    assert created["status"] == "suggested"
    try:
        confirm_mapping(store, actor, uuid.UUID(created["id"]))
        raise AssertionError("same person")
    except ForbiddenError:
        pass
    agent = _actor(kind="service_account")
    try:
        confirm_mapping(store, agent, uuid.UUID(created["id"]))
        raise AssertionError("agent")
    except ForbiddenError:
        pass
    confirmed = confirm_mapping(store, other, uuid.UUID(created["id"]))
    assert confirmed["status"] == "confirmed"
    rejected = create_mapping(
        store,
        actor,
        {
            "from_control_id": str(controls[2]["id"]),
            "to_control_id": str(controls[3]["id"]),
            "confidence": 0.2,
            "rationale": "weak",
        },
    )
    reject_mapping(store, other, uuid.UUID(rejected["id"]))
    actions = [row["action"] for row in store.audit_log]
    assert "grc.mapping.confirmed" in actions
    assert "grc.mapping.rejected" in actions
    frameworks = list(store.records["grc_frameworks"].values())
    suggested = suggest(
        store,
        actor,
        {
            "from_framework_id": str(frameworks[0]["id"]),
            "to_framework_id": str(frameworks[1]["id"]),
        },
        agent=True,
    )
    assert suggested["run_id"]
    fresh = [
        row
        for row in store.records["grc_mappings"].values()
        if row.get("rationale") == "crosswalk suggestion"
    ]
    assert fresh and all(row["status"] == "suggested" for row in fresh)


def test_evidence_link_freshness_permission_and_tenant() -> None:
    store, actor = _installed()
    control = next(iter(store.records["grc_controls"].values()))
    captured = EvidenceBook(store).capture(
        actor,
        {"media_type": "text/plain", "source_system": "desk", "collection_method": "api"},
        b"note",
    )
    evidence_id = uuid.UUID(str(captured["id"]))
    link = create_link(
        store,
        actor,
        {
            "control_id": str(control["id"]),
            "evidence_item_id": str(evidence_id),
            "freshness_days": 1,
        },
    )
    assert link["stale"] is False
    bucket(store, "evidence")[evidence_id]["collected_at"] = utcnow() - timedelta(days=10)
    stale = list_links(store, actor, {"stale": "true"})
    assert stale["items"] and stale["items"][0]["stale"] is True
    reader = _actor(permissions=frozenset({"grc.evidence:link"}))
    try:
        create_link(
            store,
            reader,
            {
                "control_id": str(control["id"]),
                "evidence_item_id": str(evidence_id),
                "freshness_days": 5,
            },
        )
        raise AssertionError("permission")
    except ForbiddenError:
        pass
    other = _actor(tenant_id=uuid.uuid4(), user_id=uuid.uuid4())
    try:
        create_link(
            store,
            other,
            {
                "control_id": str(control["id"]),
                "evidence_item_id": str(evidence_id),
                "freshness_days": 5,
            },
        )
        raise AssertionError("tenant")
    except NotFoundError:
        pass
    delete_link(store, actor, uuid.UUID(link["id"]))
    assert EvidenceBook(store).get(actor, evidence_id)["id"] == str(evidence_id)
    assert list_links(store, actor, {})["items"] == []


def test_read_tools_and_the_enable_flag() -> None:
    store, actor = _installed()
    version = next(
        row
        for row in store.tool_versions.values()
        if row["qualified_name"] == "grc.controls.search"
    )
    result = ToolPipeline(store).execute(
        {
            "tenant_id": actor.tenant_id,
            "user_id": actor.user_id,
            "synthetic": True,
            "tool_version_id": version["id"],
            "arguments": {"q": "access"},
            "model_call_id": "search",
        }
    )
    assert result["status"] == "succeeded"
    assert result["structured"]["items"]
    put_vendor(store, actor, "Northwind")
    put_policy(store, actor, "access", "Access policy", published=True)
    put_policy(store, actor, "draft", "Draft policy", published=False)
    put_answer(store, actor, "Do you encrypt disks?", status="approved")
    put_answer(
        store, actor, "Old answer", status="approved", expires_at=utcnow() - timedelta(days=1)
    )
    vendor = next(iter(store.records["grc_vendors"].values()))
    got = _tool(store, actor, "grc.vendors.get", {"vendor_id": str(vendor["id"])})
    assert got["structured"]["name"] == "Northwind"
    policies = _tool(store, actor, "grc.policies.search", {"q": "access"})
    assert len(policies["structured"]["items"]) == 1
    answers = _tool(store, actor, "grc.questionnaire.search_answers", {"q": "encrypt"})
    assert len(answers["structured"]["items"]) == 1
    obligations = _tool(store, actor, "grc.obligations.search", {"regulator": "CERT-In"})
    assert obligations["structured"]["items"]
    flag = bucket(store, "pack_flags")[(str(actor.tenant_id), "grc")]
    flag["enabled"] = False
    disabled = _tool(store, actor, "grc.controls.search", {"q": "access"})
    assert disabled["error"]["code"] == "tool_server_unavailable"


def test_entity_tree_cycle_and_sibling_grant() -> None:
    store, actor = _installed()
    parent = create_entity(store, actor, {"name": "Holdco", "kind": "legal_entity"})
    child = create_entity(
        store, actor, {"name": "East", "kind": "division", "parentId": parent["id"]}
    )
    sibling = create_entity(
        store, actor, {"name": "West", "kind": "division", "parentId": parent["id"]}
    )
    try:
        set_parent(store, actor, uuid.UUID(parent["id"]), uuid.UUID(child["id"]))
        raise AssertionError("cycle")
    except ValidationFailedError:
        pass
    from ar_pack_grc.frameworks import create_control

    create_control(
        store,
        actor,
        {"key": "east-1", "title": "East control", "entity_id": child["id"]},
    )
    create_control(
        store,
        actor,
        {"key": "west-1", "title": "West control", "entity_id": sibling["id"]},
    )
    rollup = posture(store, actor, uuid.UUID(parent["id"]))
    assert rollup["control_count"] == 2
    child_user = uuid.uuid4()
    scope_to_entity(store, actor.tenant_id, child_user, uuid.UUID(child["id"]))
    limited = _actor(user_id=child_user)
    assert posture(store, limited, uuid.UUID(child["id"]))["control_count"] == 1
    try:
        posture(store, limited, uuid.UUID(sibling["id"]))
        raise AssertionError("sibling")
    except NotFoundError:
        pass
    framework = next(iter(store.records["grc_frameworks"].values()))
    assert get_framework(store, actor, framework["id"])["key"]


def test_tenant_admin_receives_pack_permissions_only_while_enabled() -> None:
    store = ChatService()
    register_pack_permissions(store, "grc", ["grc.controls:read"])
    bucket(store, "pack_flags")[(str(demo_id("tenant")), "grc")] = {
        "tenant_id": demo_id("tenant"),
        "pack_id": "grc",
        "enabled": True,
    }
    assert permissions_for(store, demo_id("tenant"), frozenset({"tenant_admin"})) == frozenset(
        {"grc.controls:read"}
    )
    assert permissions_for(store, demo_id("tenant"), frozenset({"member"})) == frozenset()


def _tool(
    store: ChatService, actor: Actor, qualified: str, arguments: dict[str, object]
) -> dict[str, object]:
    version = next(
        row for row in store.tool_versions.values() if row["qualified_name"] == qualified
    )
    return ToolPipeline(store).execute(
        {
            "tenant_id": actor.tenant_id,
            "user_id": actor.user_id,
            "synthetic": True,
            "tool_version_id": version["id"],
            "arguments": arguments,
            "model_call_id": qualified,
        }
    )
