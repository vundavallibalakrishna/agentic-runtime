"""M19 audit desk: PBC, campaigns, entitlements, reports, privacy and resilience."""

from __future__ import annotations

import hashlib
import html
import io
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from ar_api.main import create_application
from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.records.memory import blobs, bucket
from ar_pack_grc.campaigns import (
    close_campaign,
    create_campaign,
    decide_item,
    list_items,
    start_campaign,
)
from ar_pack_grc.entitlements import ingest, list_entitlements
from ar_pack_grc.inspections import open_inspection
from ar_pack_grc.install import install_for
from ar_pack_grc.pbc import create_request, import_list, response_pdf, update_request
from ar_pack_grc.privacy import create_request as create_dsar
from ar_pack_grc.privacy import fulfil, record_consent
from ar_pack_grc.reports import render, sample_size
from ar_pack_grc.resilience import record_test
from ar_pack_grc.reviews import audited
from ar_pack_grc.risks import create_asset
from ar_pack_grc.seed_demo import seed_audit
from ar_pack_grc.sod_rules import create_rule

_GRC = frozenset(
    {
        "grc.audit_portal:manage",
        "grc.campaigns:read",
        "grc.campaigns:manage",
        "grc.reports:export",
        "grc.inspections:manage",
        "grc.privacy:manage",
        "grc.controls:read",
        "grc.controls:manage",
        "grc.risks:manage",
    }
)


def _store() -> tuple[Any, Actor]:
    app = create_application()
    actor = Actor(
        demo_id("tenant"),
        demo_id("admin"),
        PERMISSION_KEYS | _GRC,
        roles=frozenset({"tenant_admin"}),
        display_name="Admin",
    )
    install_for(app.state.chat, actor)
    return app.state.chat, actor


def test_campaign_signoff_matches_the_statement_and_force_close_needs_step_up() -> None:
    store, actor = _store()
    created = create_campaign(
        store,
        actor,
        {
            "kind": "attestation",
            "title": "Code of conduct",
            "audience": {"user_ids": [str(actor.user_id)]},
        },
    )
    started = start_campaign(store, actor, uuid.UUID(created["id"]))
    assert started["status"] == "running"
    assert audited(store, "grc.campaign.started", created["id"])
    with pytest.raises(ConflictError, match="open_items"):
        close_campaign(store, actor, uuid.UUID(created["id"]), {})
    plain = Actor(
        actor.tenant_id,
        actor.user_id,
        actor.permissions,
        roles=actor.roles,
        step_up_at=None,
    )
    with pytest.raises(ForbiddenError):
        close_campaign(store, plain, uuid.UUID(created["id"]), {"force": True})
    stepped = Actor(
        actor.tenant_id,
        actor.user_id,
        actor.permissions,
        roles=actor.roles,
        step_up_at=utcnow(),
    )
    closed = close_campaign(store, stepped, uuid.UUID(created["id"]), {"force": True})
    assert closed["status"] == "closed"
    other = create_campaign(
        store,
        actor,
        {
            "kind": "acknowledgement",
            "title": "Policy",
            "audience": {
                "user_ids": [str(actor.user_id)],
                "policy_id": str(new_id()),
            },
        },
    )
    start_campaign(store, actor, uuid.UUID(other["id"]))
    item = list_items(store, actor, {"campaign_id": other["id"]})["items"][0]
    statement = "I have read the policy."
    decided = decide_item(
        store,
        actor,
        uuid.UUID(item["id"]),
        {"decision": "acknowledge", "statement_text": statement},
    )
    digest = hashlib.sha256(statement.encode()).hexdigest()
    assert decided["statement_hash"] == digest
    assert any(row.get("statement_hash") == digest for row in store.signoffs.values())
    assert audited(store, "grc.policy.acknowledged", other["audience"]["policy_id"])
    names = {row.get("name") for row in store.routines.values()}
    assert "grc-campaign-reminder" in names
    board = next(row for row in store.routines.values() if row.get("name") == "grc-board-pack")
    delivery = board.get("delivery")
    assert isinstance(delivery, list)
    assert delivery[0]["review_before_send"] is True


def test_entitlement_ingest_is_idempotent_and_flags_business_sod() -> None:
    store, actor = _store()
    before = dict(store.sod_constraints)
    create_rule(
        store,
        actor,
        {"name": "Pay and approve", "entitlement_a": "pay", "entitlement_b": "approve"},
    )
    assert store.sod_constraints == before
    connection_id = new_id()
    bucket(store, "grc_idp_snapshots")[connection_id] = {
        "items": [
            {"subject": "ada@example.com", "entitlement": "pay"},
            {"subject": "ada@example.com", "entitlement": "approve"},
            {"subject": "ada@example.com", "entitlement": "pay"},
        ]
    }
    first = ingest(store, actor, {"source": "okta", "connection_id": str(connection_id)})
    second = ingest(store, actor, {"source": "okta", "connection_id": str(connection_id)})
    assert first["count"] == 2
    assert second["count"] == 2
    assert len(list_entitlements(store, actor, {"subject": "ada@example.com"})["items"]) == 2
    campaign = create_campaign(
        store,
        actor,
        {
            "kind": "access_review",
            "title": "Quarterly access review",
            "audience": {
                "assignees": [{"user_id": str(actor.user_id), "subject": "ada@example.com"}]
            },
        },
    )
    start_campaign(store, actor, uuid.UUID(campaign["id"]))
    item = list_items(store, actor, {"campaign_id": campaign["id"]})["items"][0]
    assert item["sod_conflicts"] == ["Pay and approve"]


def test_stranger_cannot_read_another_tenants_campaign() -> None:
    store, actor = _store()
    created = create_campaign(store, actor, {"kind": "attestation", "title": "Hidden"})
    stranger = Actor(
        uuid.uuid4(), uuid.uuid4(), actor.permissions, roles=frozenset({"tenant_admin"})
    )
    with pytest.raises(NotFoundError):
        start_campaign(store, stranger, uuid.UUID(created["id"]))


def test_pbc_grant_filter_signoff_and_watermarked_import() -> None:
    store, actor = _store()
    created = create_request(
        store,
        actor,
        {"title": "Population", "owner_user_id": str(actor.user_id)},
    )
    hidden = create_request(
        store,
        actor,
        {"title": "Hidden", "owner_user_id": str(actor.user_id)},
    )
    updated = update_request(
        store, actor, uuid.UUID(created["id"]), {"response_md": "Forty samples."}
    )
    assert updated["status"] == "responded"
    with pytest.raises(ConflictError, match="review_required"):
        update_request(store, actor, uuid.UUID(created["id"]), {"status": "provided"})
    for item in store.review_items.values():
        if str(item.get("subject_id")) == created["id"]:
            item["status"] = "signed"
    provided = update_request(store, actor, uuid.UUID(created["id"]), {"status": "provided"})
    assert provided["status"] == "provided"
    guest_id = uuid.uuid4()
    bucket(store, "guest_grants")[new_id()] = {
        "guest_id": guest_id,
        "tenant_id": actor.tenant_id,
        "portal": "auditor",
        "scope": {"pack_record_ids": [created["id"]], "binder_ids": [], "evidence_ids": []},
    }
    guest = Actor(
        actor.tenant_id,
        guest_id,
        frozenset(),
        kind="guest",
        display_name="Auditor",
    )
    from ar_pack_grc.pbc import list_requests

    visible = list_requests(store, guest)["items"]
    assert [row["id"] for row in visible] == [created["id"]]
    with pytest.raises(NotFoundError):
        response_pdf(store, guest, uuid.UUID(hidden["id"]))
    marked = response_pdf(store, guest, uuid.UUID(created["id"]))
    assert b"watermark" in marked
    assert b"Auditor" in marked
    accepted = update_request(store, guest, uuid.UUID(created["id"]), {"status": "accepted"})
    assert accepted["status"] == "accepted"
    file_id = new_id()
    owner = str(actor.user_id)
    store.files[file_id] = {"id": file_id, "tenant_id": actor.tenant_id}
    store.blobs[file_id] = _xlsx(
        [
            ["title", "owner_user_id", "due_at"],
            ["Laptop inventory", owner, (utcnow() + timedelta(days=7)).isoformat()],
        ]
    )
    imported = import_list(store, actor, {"file_id": str(file_id)})
    assert imported["count"] == 1
    assert imported["items"][0]["title"] == "Laptop inventory"


def test_reports_render_a_verifiable_binder_and_hold_the_board_pack() -> None:
    store, actor = _store()
    control_id = new_id()
    bucket(store, "grc_controls")[control_id] = {
        "id": control_id,
        "tenant_id": actor.tenant_id,
        "key": "iso-1",
        "title": "Access",
        "statement": "The organization shall retain the licensed text.",
    }
    assert sample_size(10) == 10
    assert sample_size(26) == 7
    rendered = render(store, actor, {"template": "soa", "params": {}})
    payload = blobs(store, "binders")[uuid.UUID(str(rendered["binder_id"]))]
    assert isinstance(payload, bytes)
    assert b"The organization shall" not in payload
    assert b"iso-1" in payload
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "binder.zip"
        path.write_bytes(payload)
        checked = subprocess.run(  # noqa: S603
            [sys.executable, "scripts/verify_binder.py", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    assert checked.returncode == 0, checked.stderr
    for template in ("soc2_binder", "cscrf", "dpdp_breach"):
        body = render(store, actor, {"template": template, "params": {"population": 40}})
        assert body["status"] == "ready"
        assert audited(store, "grc.report.exported", body["binder_id"])
    board = render(store, actor, {"template": "board_pack", "params": {}})
    assert board["status"] == "pending_review"
    saved = bucket(store, "binders")[uuid.UUID(str(board["binder_id"]))]
    assert saved.get("file_id") is None


def test_inspection_grant_is_one_binder_and_privacy_skips_a_hold() -> None:
    store, actor = _store()
    opened = open_inspection(store, actor, {"regulator": "SEBI", "started_on": "2026-10-28"})
    assert audited(store, "grc.inspection.opened", opened["id"])
    guest = Actor(
        actor.tenant_id,
        uuid.UUID(str(opened["guest_id"])),
        frozenset(),
        kind="guest",
        display_name="SEBI",
    )
    from ar_domain.records.binders import BinderBook

    BinderBook(store).get(guest, uuid.UUID(str(opened["binder_id"])))
    other = BinderBook(store).create(actor, {"title": "Second", "selection": {}})
    with pytest.raises(NotFoundError):
        BinderBook(store).get(guest, uuid.UUID(str(other["id"])))
    subject = uuid.uuid4()
    held_id = new_id()
    loose_id = new_id()
    evidence = bucket(store, "evidence")
    evidence[held_id] = {
        "id": held_id,
        "tenant_id": actor.tenant_id,
        "collector_principal_id": subject,
    }
    evidence[loose_id] = {
        "id": loose_id,
        "tenant_id": actor.tenant_id,
        "collector_principal_id": subject,
    }
    hold_id = new_id()
    bucket(store, "holds")[hold_id] = {
        "id": hold_id,
        "tenant_id": actor.tenant_id,
        "status": "active",
    }
    bucket(store, "hold_members")[new_id()] = {
        "hold_id": hold_id,
        "record_class": "evidence_item",
        "record_id": held_id,
    }
    file_id = new_id()
    store.files[file_id] = {"id": file_id, "tenant_id": actor.tenant_id, "user_id": subject}
    request = create_dsar(
        store,
        actor,
        {
            "request_type": "erasure",
            "due_at": (utcnow() + timedelta(days=10)).isoformat(),
            "subject_user_id": str(subject),
        },
    )
    with pytest.raises(ConflictError, match="review_required"):
        fulfil(store, actor, uuid.UUID(request["id"]))
    for item in store.review_items.values():
        if str(item.get("subject_id")) == request["id"]:
            item["status"] = "signed"
    done = fulfil(store, actor, uuid.UUID(request["id"]))
    assert done["status"] == "fulfilled"
    assert str(held_id) in done["held_record_ids"]
    assert held_id in evidence
    assert loose_id not in evidence
    assert file_id not in store.files
    with pytest.raises(ValidationFailedError, match="evidence is required"):
        record_consent(
            store,
            actor,
            {"subject_ref": "ada", "purpose": "mail", "state": "granted"},
        )
    record_consent(
        store,
        actor,
        {
            "subject_ref": "ada",
            "purpose": "mail",
            "state": "granted",
            "evidence_item_id": str(held_id),
        },
    )
    with pytest.raises(ValidationFailedError, match="evidence is required"):
        record_test(store, actor, {"kind": "dr", "tested_on": "2026-10-01", "outcome": "fail"})
    recorded = record_test(
        store,
        actor,
        {
            "kind": "dr",
            "tested_on": "2026-10-01",
            "outcome": "fail",
            "evidence_item_id": str(held_id),
        },
    )
    assert recorded["outcome"] == "fail"
    cards = bucket(store, "agent_cards")
    before_cards = len(cards)
    before_agents = len(store.agents)
    asset = create_asset(
        store,
        actor,
        {
            "name": "Support assistant",
            "kind": "model",
            "owner_user_id": str(actor.user_id),
            "tier": "high",
        },
    )
    assert asset["kind"] == "model"
    assert asset["agent_card_id"] is None
    assert len(cards) == before_cards
    assert len(store.agents) == before_agents
    with pytest.raises(ValidationFailedError, match="tier is required"):
        create_asset(
            store,
            actor,
            {"name": "Bare model", "kind": "model", "owner_user_id": str(actor.user_id)},
        )
    seed_audit(store, actor)
    seed_audit(store, actor)


def _xlsx(rows: list[list[str]]) -> bytes:
    body = []
    for index, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c t="inlineStr"><is><t>{html.escape(value)}</t></is></c>' for value in row
        )
        body.append(f'<row r="{index}">{cells}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(body)}</sheetData></worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()
