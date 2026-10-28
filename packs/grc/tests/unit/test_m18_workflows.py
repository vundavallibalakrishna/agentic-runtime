"""Questionnaires, vendors, policies, risks, watchers, incidents, exceptions and ethics."""

import uuid
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.approvals.reviews import ReviewBook
from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.records.memory import bucket
from ar_pack_grc.ethics import get_case, open_case
from ar_pack_grc.exceptions import covering_exception, create_exception, expire_due, sync_signed
from ar_pack_grc.incidents import create_incident, file_notification, get_incident, start_clock
from ar_pack_grc.install import install_for
from ar_pack_grc.mcp_server import handle
from ar_pack_grc.policies import add_version, create_policy, publish, revise_draft, submit_review
from ar_pack_grc.questionnaires import (
    create_answer,
    draft_job,
    draft_text,
    export_job,
    open_reviews,
    search_answers,
    sync_approvals,
)
from ar_pack_grc.regulatory import (
    classify_circular,
    create_feed,
    fetch_feed,
    list_obligations,
    sample_size,
    triage,
)
from ar_pack_grc.risks import accept_risk, create_risk, get_risk, patch_risk
from ar_pack_grc.tests import create_test, record_result
from ar_pack_grc.vendors import (
    create_assessment,
    create_vendor,
    get_assessment_for_guest,
    list_assessments,
    review_soc2,
    score_assessment,
)

PERMS = PERMISSION_KEYS | frozenset(
    {
        "grc.frameworks:read",
        "grc.controls:read",
        "grc.controls:manage",
        "grc.questionnaires:read",
        "grc.questionnaires:manage",
        "grc.vendors:read",
        "grc.vendors:manage",
        "grc.policies:read",
        "grc.policies:manage",
        "grc.risks:read",
        "grc.risks:manage",
        "grc.obligations:read",
        "grc.obligations:manage",
        "grc.incidents:read",
        "grc.incidents:manage",
        "grc.exceptions:manage",
        "grc.ethics:manage",
        "grc.tests:run",
        "grc.campaigns:read",
        "reviews:decide",
        "evidence:read",
    }
)


def _actor(user_id: uuid.UUID | None = None, permissions: frozenset[str] | None = None) -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=user_id or demo_id("admin"),
        permissions=permissions or PERMS,
        roles=frozenset({"tenant_admin"}),
    )


def _installed() -> tuple[ChatService, Actor]:
    store = ChatService()
    actor = _actor()
    install_for(store, actor)
    return store, actor


def _sign(store: ChatService, item: dict[str, object]) -> None:
    signer = _actor(user_id=demo_id("approver"))
    ReviewBook(store).decide(
        signer,
        uuid.UUID(str(item["id"])),
        {
            "decision": "approve",
            "content_hash": item["content_hash"],
            "statement_hash": item["statement_hash"],
        },
        stepped_up=True,
    )


def _audits(store: ChatService, action: str) -> list[dict[str, object]]:
    return [row for row in store.audit_log if row.get("action") == action]


def test_ungrounded_draft_is_blank_and_expired_answers_are_hidden() -> None:
    store, actor = _installed()
    create_answer(
        store,
        actor,
        {
            "question": "Do you encrypt disks?",
            "answer_md": "Disks are encrypted at rest.",
            "citations": ["evidence:disks"],
        },
    )
    row = next(iter(bucket(store, "grc_answers").values()))
    row["status"] = "approved"
    blank = draft_text(store, actor, "Where is the backup site?")
    assert blank["answer_md"] == ""
    assert blank["grounded"] is False
    grounded = draft_text(store, actor, "encrypt")
    assert "[1]" in str(grounded["answer_md"])
    assert "Disks are encrypted" in str(grounded["answer_md"])
    create_answer(store, actor, {"question": "Old encrypt standard?", "answer_md": "Retired."})
    old = next(
        row for row in bucket(store, "grc_answers").values() if row["question"].startswith("Old")
    )
    old["status"] = "approved"
    old["expires_at"] = utcnow() - timedelta(days=1)
    assert search_answers(store, actor, "Old") == []
    assert len(search_answers(store, actor, "encrypt disks")) == 1


def test_export_refuses_an_unapproved_answer_and_bulk_review_approves_one_hundred() -> None:
    store, actor = _installed()
    file_id = new_id()
    store.blobs[file_id] = b"What is the retention period?\n"
    started = draft_job(store, actor, {"file_id": str(file_id)})
    job_id = uuid.UUID(str(started["job_id"]))
    with pytest.raises(ConflictError, match="review_required"):
        export_job(store, actor, job_id)
    ids = []
    for index in range(100):
        created = create_answer(
            store, actor, {"question": f"Bulk {index}", "answer_md": f"Answer {index}."}
        )
        ids.append(uuid.UUID(str(created["id"])))
    opened = open_reviews(store, actor, ids)
    assert len(opened) == 100
    ReviewBook(store).bulk(
        _actor(user_id=demo_id("approver")),
        {
            "decision": "approve",
            "items": [
                {
                    "review_item_id": item["id"],
                    "content_hash": item["content_hash"],
                    "statement_hash": item["statement_hash"],
                }
                for item in opened
            ],
        },
        stepped_up=True,
    )
    assert sync_approvals(store, actor) == 100
    assert (
        sum(1 for row in bucket(store, "grc_answers").values() if row.get("status") == "approved")
        >= 100
    )


def test_guest_sees_only_granted_assessments_and_soc2_skill_reads_the_fixture() -> None:
    store, actor = _installed()
    vendor = create_vendor(store, actor, {"name": "Northwind"})
    vendor_id = uuid.UUID(str(vendor["id"]))
    first = create_assessment(store, actor, vendor_id, {"kind": "document_review"})
    second = create_assessment(store, actor, vendor_id, {"kind": "questionnaire"})
    guest = Actor(actor.tenant_id, uuid.uuid4(), frozenset(), kind="guest")
    bucket(store, "guest_grants")[new_id()] = {
        "id": new_id(),
        "tenant_id": actor.tenant_id,
        "guest_id": guest.user_id,
        "portal": "vendor",
        "scope": {"pack_record_ids": [str(first["id"])]},
    }
    visible = list_assessments(store, guest, vendor_id)["items"]
    assert [item["id"] for item in visible] == [str(first["id"])]
    assert get_assessment_for_guest(store, guest, uuid.UUID(str(first["id"])))["id"] == str(
        first["id"]
    )
    try:
        get_assessment_for_guest(store, guest, uuid.UUID(str(second["id"])))
        raise AssertionError("scope")
    except NotFoundError:
        pass
    member = Actor(actor.tenant_id, uuid.uuid4(), frozenset({"grc.controls:read"}))
    try:
        list_assessments(store, member, vendor_id)
        raise AssertionError("read")
    except ForbiddenError:
        pass
    scored = score_assessment(
        store,
        actor,
        uuid.UUID(str(first["id"])),
        {"tier": "high", "rationale": "Exceptions are open."},
    )
    assert scored["tier"] == "high"
    assert _audits(store, "grc.assessment.completed")
    report = Path("packs/grc/tests/fixtures/soc2-report.txt").read_text(encoding="utf-8")
    extracted = review_soc2(report)
    assert extracted["exceptions"] == [
        "Backup jobs missed the nightly window for three days in June."
    ]
    assert extracted["cuecs"]
    assert extracted["bridge_letter_gaps"]
    assert any(row.get("slug") == "soc2-report-review" for row in store.skills.values())


def test_publish_waits_for_sign_off_and_a_new_hash_supersedes_the_review() -> None:
    store, actor = _installed()
    policy = create_policy(store, actor, {"key": "access", "title": "Access control"})
    policy_id = uuid.UUID(str(policy["id"]))
    version = add_version(store, actor, policy_id, {"body_md": "Grant access to a named role."})
    version_id = uuid.UUID(str(version["id"]))
    opened = submit_review(store, actor, policy_id)
    with pytest.raises(ConflictError, match="review_required"):
        publish(store, actor, version_id)
    revise_draft(store, actor, version_id, "Grant access to a named role and review it quarterly.")
    assert store.review_items[uuid.UUID(str(opened["review_item"]["id"]))]["status"] == "superseded"
    again = submit_review(store, actor, policy_id)
    _sign(store, again["review_item"])
    published = publish(store, actor, version_id)
    assert published["state"] == "published"
    assert len(_audits(store, "grc.policy.published")) == 1
    publish(store, actor, version_id)
    assert len(_audits(store, "grc.policy.published")) == 1
    assert any(
        row.get("kind") == "acknowledgement" for row in bucket(store, "grc_campaigns").values()
    )


def test_score_history_and_acceptance_audit_wait_for_sign_off() -> None:
    store, actor = _installed()
    risk = create_risk(
        store,
        actor,
        {
            "title": "Vendor outage",
            "statement": "A vendor misses the restore window.",
            "likelihood": 2,
            "impact": 3,
        },
    )
    risk_id = uuid.UUID(str(risk["id"]))
    assert risk["assessments"][0]["score"] == 6
    changed = patch_risk(store, actor, risk_id, {"likelihood": 4, "impact": 5})
    assert len(changed["assessments"]) == 2
    assert changed["assessments"][-1]["score"] == 20
    proposed = accept_risk(
        store,
        actor,
        risk_id,
        {
            "statement_text": "Accept until the exit plan is signed.",
            "expires_at": (utcnow() + timedelta(days=30)).isoformat(),
        },
    )
    assert proposed["status"] == "proposed"
    assert _audits(store, "grc.risk.accepted") == []
    _sign(store, store.review_items[uuid.UUID(str(proposed["acceptance"]["review_item_id"]))])
    assert get_risk(store, actor, risk_id)["status"] == "accepted"
    assert _audits(store, "grc.risk.accepted")
    proposed_by_agent = handle(
        store,
        "risks_propose",
        {
            "_tenant_id": str(actor.tenant_id),
            "_user_id": str(actor.user_id),
            "title": "Model drift",
            "statement": "Scores move without a review.",
            "likelihood": 3,
            "impact": 3,
        },
        "",
    )
    assert proposed_by_agent["is_error"] is False
    assert _audits(store, "grc.risk.proposed")


def test_fetch_stops_for_robots_and_private_urls_and_classifies_hindi() -> None:
    store, actor = _installed()

    def resolver(_host: str) -> list[str]:
        return ["93.184.216.34"]

    def pages(url: str) -> tuple[int, str]:
        if url.endswith("/robots.txt"):
            return 200, "User-agent: *\nDisallow: /\n"
        return 200, "Circular\nBody"

    feed = create_feed(
        store,
        actor,
        {"regulator": "Example", "url": "https://example.com/circulars"},
        resolver=resolver,
    )
    with pytest.raises(ForbiddenError, match="robots_denied"):
        fetch_feed(store, actor, uuid.UUID(str(feed["id"])), getter=pages, resolver=resolver)
    try:
        create_feed(store, actor, {"regulator": "Local", "url": "http://10.1.1.1/feed"})
        raise AssertionError("ssrf")
    except ForbiddenError:
        pass

    def open_pages(url: str) -> tuple[int, str]:
        if url.endswith("/robots.txt"):
            return 404, ""
        return 200, "DPDP circular\nNotify within 72 hours."

    change = fetch_feed(
        store, actor, uuid.UUID(str(feed["id"])), getter=open_pages, resolver=resolver
    )
    assert change["status"] == "new"
    document_id = uuid.UUID(str(change["document_id"]))
    assert store.knowledge_documents[document_id]["collection_id"]
    obligation = list_obligations(store, actor, {"regulator": "DPDP"})["items"][0]
    triaged = triage(
        store,
        actor,
        uuid.UUID(str(change["id"])),
        {
            "relevant": True,
            "obligation_ids": [obligation["id"]],
            "control_ids": [],
            "note": "Applies.",
        },
    )
    assert triaged["obligation_ids"] == [obligation["id"]]
    assert _audits(store, "grc.regulatory_change.triaged")
    suite = yaml.safe_load(
        Path("packs/grc/evals/regulatory/hindi-circular.yaml").read_text(encoding="utf-8")
    )
    text = suite["cases"][0]["input"]["messages"][0]
    classified = classify_circular(text)
    assert classified["language"] == "hi"
    assert classified["regulator"] == "DPDP"
    assert "Rules 2025 rule 7" in classified["obligation_citations"]
    assert sample_size(25) == 25
    assert sample_size(26) == 7
    assert any(row.get("slug") == "cscrf-sampling" for row in store.skills.values())


def test_clocks_are_idempotent_and_filing_waits_for_sign_off() -> None:
    store, actor = _installed()
    before = len(bucket(store, "holds"))
    incident = create_incident(
        store,
        actor,
        {
            "title": "Lost laptop",
            "detected_at": utcnow().isoformat(),
            "summary": "Extract left the building.",
        },
    )
    assert len(bucket(store, "holds")) == before
    incident_id = uuid.UUID(str(incident["id"]))
    cert = start_clock(store, actor, incident_id, {"regime": "cert_in"})
    dpdp = start_clock(store, actor, incident_id, {"regime": "dpdp"})
    again = start_clock(store, actor, incident_id, {"regime": "dpdp"})
    assert cert["duration_seconds"] == 6 * 3600
    assert dpdp["duration_seconds"] == 72 * 3600
    assert again["id"] == dpdp["id"]
    assert len(store.grc_timers) == 2
    gdpr = start_clock(store, actor, incident_id, {"regime": "gdpr"})
    assert gdpr["duration_seconds"] == 72 * 3600
    note = file_notification(
        store, actor, incident_id, {"regime": "dpdp", "body_md": "We will notify the Board."}
    )
    assert _audits(store, "grc.incident.notified") == []
    _sign(store, store.review_items[uuid.UUID(str(note["review_item_id"]))])
    filed = get_incident(store, actor, incident_id)
    assert filed["status"] == "notified"
    assert _audits(store, "grc.incident.notified")
    draft = handle(
        store,
        "incidents_update_draft",
        {
            "_tenant_id": str(actor.tenant_id),
            "_user_id": str(actor.user_id),
            "incident_id": str(incident_id),
            "body_md": "Draft only.",
        },
        "",
    )
    assert draft["structured"]["draft_md"] == "Draft only."


def test_waiver_requires_a_control_and_an_expired_exception_is_ignored() -> None:
    store, actor = _installed()
    controls = [
        row
        for row in bucket(store, "grc_controls").values()
        if row.get("tenant_id") == actor.tenant_id
    ]
    control_id = controls[0]["id"]
    other_id = controls[1]["id"]
    with pytest.raises(ValidationFailedError, match="compensating_control_id"):
        create_exception(
            store,
            actor,
            {
                "control_id": str(control_id),
                "kind": "waiver",
                "rationale": "No compensating control.",
                "expires_at": (utcnow() + timedelta(days=5)).isoformat(),
            },
        )
    created = create_exception(
        store,
        actor,
        {
            "control_id": str(control_id),
            "kind": "waiver",
            "rationale": "Isolated until cutover.",
            "compensating_control_id": str(other_id),
            "expires_at": (utcnow() + timedelta(days=5)).isoformat(),
        },
    )
    assert created["status"] == "proposed"
    assert _audits(store, "grc.exception.signed") == []
    _sign(store, store.review_items[uuid.UUID(str(created["review_item_id"]))])
    assert sync_signed(store, actor) == 1
    assert covering_exception(store, actor, control_id)["id"] == uuid.UUID(str(created["id"]))
    row = bucket(store, "grc_exceptions")[uuid.UUID(str(created["id"]))]
    row["expires_at"] = utcnow() - timedelta(minutes=1)
    assert expire_due(store, actor) == 1
    assert covering_exception(store, actor, control_id) is None
    test = create_test(
        store,
        actor,
        {
            "control_id": str(control_id),
            "key": "expiry",
            "procedure": "Check the control.",
            "schedule": "0 6 * * *",
            "freshness_days": 30,
        },
    )
    recorded = record_result(
        store, actor, {"test_id": test["id"], "outcome": "fail", "summary": "Still failing."}
    )
    assert recorded["exception_id"] is None
    assert any(row.get("name") == "grc-exception-expiry" for row in store.routines.values())


def test_ethics_case_is_hidden_from_an_auditor_and_does_not_open_a_hold() -> None:
    store, actor = _installed()
    before = len(bucket(store, "holds"))
    opened = open_case(store, actor, {"title": "Unsolicited gift"})
    assert len(bucket(store, "holds")) == before
    assert _audits(store, "grc.ethics.opened")
    auditor = Actor(
        actor.tenant_id,
        uuid.uuid4(),
        frozenset({"audit:read", "reviews:read", "evidence:read"}),
        roles=frozenset({"auditor"}),
    )
    try:
        get_case(store, auditor, uuid.UUID(str(opened["id"])))
        raise AssertionError("hidden")
    except NotFoundError:
        pass
    other = _actor(user_id=uuid.uuid4())
    other = Actor(uuid.uuid4(), other.user_id, PERMS, roles=frozenset({"tenant_admin"}))
    try:
        get_case(store, other, uuid.UUID(str(opened["id"])))
        raise AssertionError("tenant")
    except NotFoundError:
        pass


def test_templates_carry_strict_grounding() -> None:
    store, _who = _installed()
    answerer = next(
        row for row in store.agents.values() if row.get("slug") == "questionnaire-answerer"
    )
    definition = answerer["definition"]
    assert definition["output"] == {"citations": "required", "grounding": "strict"}
    assert definition["assurance"] == {"recordMode": "on"}
    assert definition["model"]["params"]["temperature"] == 0
    assert any(row.get("name") == "grc-regulatory-poll" for row in store.routines.values())
