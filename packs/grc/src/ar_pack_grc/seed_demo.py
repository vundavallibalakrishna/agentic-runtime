"""Demo rows for the workflow screens. Tests call install_for and skip this."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.records.memory import bucket
from ar_pack_grc.access import owned
from ar_pack_grc.campaigns import create_campaign
from ar_pack_grc.entitlements import ingest
from ar_pack_grc.exceptions import create_exception
from ar_pack_grc.incidents import create_incident, start_clock
from ar_pack_grc.inspections import open_inspection
from ar_pack_grc.pbc import create_request
from ar_pack_grc.policies import add_version, create_policy
from ar_pack_grc.privacy import create_request as create_dsar
from ar_pack_grc.privacy import record_consent
from ar_pack_grc.questionnaires import create_answer, draft_job
from ar_pack_grc.regulatory import create_feed, fetch_feed
from ar_pack_grc.resilience import record_test
from ar_pack_grc.risks import create_asset, create_risk
from ar_pack_grc.sod_rules import create_rule
from ar_pack_grc.vendors import create_assessment, create_vendor

if TYPE_CHECKING:
    from typing import Any

_PERMS = frozenset(
    {
        "grc.questionnaires:manage",
        "grc.questionnaires:read",
        "grc.vendors:manage",
        "grc.policies:manage",
        "grc.risks:manage",
        "grc.obligations:manage",
        "grc.incidents:manage",
        "grc.exceptions:manage",
        "grc.controls:read",
        "grc.ethics:manage",
        "reviews:decide",
    }
)


def seed_audit(store: Any, actor: Actor) -> None:
    """Rows for the audit desk. Idempotent, and skipped when the PBC title exists."""
    if any(
        row.get("title") == "SOC 2 population extract"
        for row in owned(store, "grc_pbc_requests", actor)
    ):
        return
    who = Actor(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        permissions=actor.permissions | _AUDIT,
        roles=actor.roles or frozenset({"tenant_admin"}),
        display_name=actor.display_name,
        step_up_at=utcnow(),
    )
    create_request(
        store,
        who,
        {
            "title": "SOC 2 population extract",
            "owner_user_id": str(who.user_id),
            "due_at": (utcnow() + timedelta(days=21)).isoformat(),
        },
    )
    create_rule(
        store,
        who,
        {"name": "Pay and approve", "entitlement_a": "pay", "entitlement_b": "approve"},
    )
    connection_id = new_id()
    bucket(store, "grc_idp_snapshots")[connection_id] = {
        "items": [
            {"subject": "ada@example.com", "entitlement": "pay"},
            {"subject": "ada@example.com", "entitlement": "approve"},
        ]
    }
    ingest(store, who, {"source": "okta", "connection_id": str(connection_id)})
    create_campaign(
        store,
        who,
        {
            "kind": "access_review",
            "title": "Quarterly access review",
            "due_at": (utcnow() + timedelta(days=14)).isoformat(),
            "audience": {
                "assignees": [{"user_id": str(who.user_id), "subject": "ada@example.com"}]
            },
        },
    )
    open_inspection(
        store, who, {"regulator": "SEBI", "started_on": utcnow().date().isoformat()}
    )
    create_dsar(
        store,
        who,
        {
            "request_type": "access",
            "due_at": (utcnow() + timedelta(days=30)).isoformat(),
            "subject_user_id": str(who.user_id),
        },
    )
    evidence_id = new_id()
    bucket(store, "evidence")[evidence_id] = {
        "id": evidence_id,
        "tenant_id": who.tenant_id,
        "status": "sealed",
        "media_type": "text/plain",
    }
    record_consent(
        store,
        who,
        {
            "subject_ref": "customer-1842",
            "purpose": "Account notices",
            "state": "granted",
            "evidence_item_id": str(evidence_id),
        },
    )
    record_test(
        store,
        who,
        {
            "kind": "bcp",
            "tested_on": utcnow().date().isoformat(),
            "outcome": "pass",
            "evidence_item_id": str(evidence_id),
        },
    )
    create_asset(
        store,
        who,
        {
            "name": "Support assistant",
            "kind": "model",
            "owner_user_id": str(who.user_id),
            "tier": "high",
        },
    )


_AUDIT = frozenset(
    {
        "grc.audit_portal:manage",
        "grc.campaigns:manage",
        "grc.campaigns:read",
        "grc.reports:export",
        "grc.inspections:manage",
        "grc.privacy:manage",
        "grc.controls:manage",
        "grc.controls:read",
        "grc.risks:manage",
        "binders:export",
        "guests:invite",
        "users:manage",
    }
)


def seed_workflows(store: Any, actor: Actor) -> None:
    if any(row.get("name") == "Northwind" for row in owned(store, "grc_vendors", actor)):
        return
    who = Actor(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        permissions=actor.permissions | _PERMS,
        roles=actor.roles or frozenset({"tenant_admin"}),
        display_name=actor.display_name,
    )
    create_answer(
        store,
        who,
        {
            "question": "Do you encrypt disks?",
            "answer_md": "Disks are encrypted at rest.",
            "citations": ["evidence:disks"],
            "status": "approved",
        },
    )
    # create_answer always stores draft. Approve it for the library search.
    saved = next(iter(bucket(store, "grc_answers").values()))
    saved["status"] = "approved"
    file_id = new_id()
    store.blobs[file_id] = b"Do you encrypt disks?\nWhere is the backup site?\n"
    store.files[file_id] = {"id": file_id, "tenant_id": who.tenant_id, "status": "ready"}
    draft_job(store, who, {"file_id": str(file_id)})
    vendor = create_vendor(store, who, {"name": "Northwind", "owner_user_id": str(who.user_id)})
    create_assessment(
        store,
        who,
        uuid.UUID(str(vendor["id"])),
        {"kind": "document_review", "due_at": (utcnow() + timedelta(days=14)).isoformat()},
    )
    policy = create_policy(
        store, who, {"key": "access", "title": "Access control", "owner_user_id": str(who.user_id)}
    )
    add_version(
        store,
        who,
        uuid.UUID(str(policy["id"])),
        {"body_md": "Access is granted to a named role. [1]", "change_note": "First draft"},
    )
    asset = create_asset(store, who, {"name": "Customer vault", "kind": "system"})
    create_risk(
        store,
        who,
        {
            "title": "Vendor outage",
            "statement": "A critical vendor cannot restore service within the agreed window.",
            "asset_id": asset["id"],
            "likelihood": 3,
            "impact": 4,
        },
    )
    _circular(store, who)
    incident = create_incident(
        store,
        who,
        {
            "title": "Laptop with customer extracts",
            "detected_at": utcnow().isoformat(),
            "summary": "A laptop left the office with a customer extract.",
        },
    )
    start_clock(store, who, uuid.UUID(str(incident["id"])), {"regime": "dpdp"})
    controls = owned(store, "grc_controls", who)
    if len(controls) >= 2:
        create_exception(
            store,
            who,
            {
                "control_id": str(controls[0]["id"]),
                "kind": "waiver",
                "rationale": "The legacy store is isolated until the quarter closes.",
                "compensating_control_id": str(controls[1]["id"]),
                "expires_at": (utcnow() + timedelta(days=30)).isoformat(),
            },
        )
    from ar_pack_grc.ethics import open_case  # noqa: PLC0415

    open_case(store, who, {"title": "Unsolicited gift from a supplier"})


def _circular(store: Any, actor: Actor) -> None:
    def resolver(_host: str) -> list[str]:
        return ["93.184.216.34"]

    def getter(url: str) -> tuple[int, str]:
        if url.endswith("/robots.txt"):
            return 404, ""
        return 200, "DPDP circular\nA personal data breach is intimated within 72 hours."

    feed = create_feed(
        store,
        actor,
        {"regulator": "MeitY / DPB", "url": "https://example.com/dpdp-circular"},
        resolver=resolver,
    )
    fetch_feed(store, actor, uuid.UUID(str(feed["id"])), getter=getter, resolver=resolver)
