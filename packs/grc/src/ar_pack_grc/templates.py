"""Publish the pack agent templates, skills and routines."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

from ar_common.errors import ArError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.routines.book import RoutineBook
from ar_domain.skills.book import SkillBook

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_SHARED: dict[str, object] = {
    "visibility": "tenant",
    "riskTier": "medium",
    "model": {
        "alias": "reasoning",
        "fastAlias": "fast",
        "degradeToFast": False,
        "params": {"temperature": 0},
    },
    "toolSearch": {"mode": "off"},
    "memory": {"enabled": False},
    "sandbox": {"enabled": False},
    "channels": {
        "web": True,
        "slack": False,
        "teams": False,
        "email": False,
        "api": True,
        "widget": False,
    },
    "budget": {
        "maxSteps": 20,
        "maxTokens": 200000,
        "maxCostMicros": 20000000,
        "maxWallClockS": 900,
        "maxToolCalls": 40,
        "maxParallelToolCalls": 2,
    },
    "output": {"citations": "required", "grounding": "strict"},
    "assurance": {"recordMode": "on"},
}

_AGENTS: tuple[dict[str, object], ...] = (
    {
        "slug": "questionnaire-answerer",
        "name": "Questionnaire answerer",
        "description": "Drafts answers from the approved library.",
        "instructions": (
            "Search the answer library and published policies. Draft one answer per "
            "question with citations. If nothing grounds the answer, say so and "
            "leave the answer blank. Do not write the library."
        ),
        "tools": ["questionnaire.search_answers", "questionnaire.draft_answer", "policies.search"],
    },
    {
        "slug": "vendor-assessor",
        "name": "Vendor assessor",
        "description": "Reviews vendor documents and proposes a tier.",
        "instructions": (
            "Read the vendor and the uploaded evidence. Use the soc2-report-review "
            "skill for SOC 2 reports. Propose a tier with a rationale that cites "
            "evidence item ids. Do not complete the assessment yourself."
        ),
        "tools": ["vendors.get"],
        "skills": ["soc2-report-review"],
    },
    {
        "slug": "policy-drafter",
        "name": "Policy drafter",
        "description": "Drafts a policy version from the catalogue and current policies.",
        "instructions": (
            "Draft markdown that cites the control ids it implements. Do not "
            "publish. The review queue publishes."
        ),
        "tools": ["controls.search", "policies.search"],
    },
    {
        "slug": "regulatory-watcher",
        "name": "Regulatory watcher",
        "description": "Classifies a fetched circular and lists impacted obligations.",
        "instructions": (
            "Classify the document. List obligation and control ids it may affect. "
            "Do not triage; a person calls :triage."
        ),
        "tools": ["obligations.search", "controls.search", "policies.search"],
    },
    {
        "slug": "risk-analyst",
        "name": "Risk analyst",
        "description": "Proposes risks from findings and scores them.",
        "instructions": (
            "Use the risk-scoring skill. Propose risks with likelihood and impact "
            "on the 1..5 scale. Do not accept a risk."
        ),
        "tools": ["risks.propose", "controls.get"],
        "skills": ["risk-scoring"],
        "sandbox": {"enabled": True, "template": "default", "scope": "conversation"},
    },
    {
        "slug": "incident-coordinator",
        "name": "Incident coordinator",
        "description": "Drafts breach notifications against a running clock.",
        "instructions": (
            "Use the dpdp-breach-assessment skill for DPDP. Draft the notification. "
            "Do not call :file-notification and do not start a clock."
        ),
        "tools": ["incidents.update_draft", "obligations.search"],
        "skills": ["dpdp-breach-assessment"],
    },
    {
        "slug": "control-tester",
        "name": "Control tester",
        "description": "Runs one control test and records the outcome.",
        "instructions": (
            "Run the procedure on the control test. Call records.capture for each "
            "artefact you keep. Call grc.tests.record_result with outcome pass, "
            "fail or error. On fail, call grc.findings.create. Do not invent a "
            "pass."
        ),
        "tools": ["controls.get", "tests.record_result", "findings.create", "evidence.attach"],
    },
    {
        "slug": "evidence-collector",
        "name": "Evidence collector",
        "description": "Collects read-only evidence and links it to a control.",
        "instructions": (
            "Use only the connector tools granted on this run. Capture each kept "
            "response with records.capture. Link it with grc.evidence.attach. Never "
            "call a write tool."
        ),
        "tools": ["controls.get", "evidence.attach"],
    },
    {
        "slug": "pbc-responder",
        "name": "PBC responder",
        "description": "Matches an auditor request to controls and evidence.",
        "instructions": (
            "For each PBC request, search controls and list evidence links. Draft a "
            "response that cites evidence item ids. Do not mark the request "
            "provided."
        ),
        "tools": ["controls.search", "controls.get"],
    },
    {
        "slug": "crosswalk-mapper",
        "name": "Crosswalk mapper",
        "description": "Suggests control mappings for a human to confirm.",
        "instructions": (
            "Suggest mappings with a rationale and a confidence from 0 to 1. Never "
            "confirm a mapping."
        ),
        "tools": ["controls.search", "controls.get", "mapping.suggest"],
        "skills": ["oscal-handling"],
    },
    {
        "slug": "remediation-tracker",
        "name": "Remediation tracker",
        "description": "Drafts issue updates and checks closure evidence.",
        "instructions": (
            "Summarise open issues past due. For a closure request, call "
            "records.verify and refuse to recommend close when verification fails."
        ),
        "tools": ["controls.get"],
        "skills": ["cscrf-atr"],
    },
    {
        "slug": "access-review-coordinator",
        "name": "Access review coordinator",
        "description": "Summarises entitlement conflicts for reviewers.",
        "instructions": (
            "List entitlements that match a business SoD rule. Do not decide campaign items."
        ),
        "tools": ["controls.search"],
    },
    {
        "slug": "board-reporter",
        "name": "Board reporter",
        "description": "Drafts the board pack narrative from pack counts.",
        "instructions": (
            "Write the narrative from tool results only. Do not send the report. "
            "Delivery waits for reviewBeforeSend."
        ),
        "tools": ["controls.search", "obligations.search"],
    },
)

_SKILLS: tuple[dict[str, object], ...] = (
    {
        "slug": "soc2-report-review",
        "name": "SOC 2 report review",
        "description": "Extract exceptions, CUECs and bridge-letter gaps from a SOC 2 report.",
        "tools": ["records.get"],
        "instructions": (
            "Cite the evidence item. List exceptions, complementary user-entity "
            "controls, and whether a bridge letter covers the period."
        ),
    },
    {
        "slug": "dpdp-breach-assessment",
        "name": "DPDP breach assessment",
        "description": "Assess whether a personal-data breach needs a DPDP Rule 7 intimation.",
        "tools": ["grc.obligations.search"],
        "instructions": (
            "State the facts you have, the 72 hour clock if one is running, and the "
            "gaps a DPO must fill. Do not decide filing."
        ),
    },
    {
        "slug": "cscrf-atr",
        "name": "CSCRF action-taken report",
        "description": "Draft a CSCRF action-taken report from findings and closure evidence.",
        "tools": ["records.verify"],
        "instructions": (
            "One row per finding: requirement id, action, evidence item id, verification result."
        ),
    },
    {
        "slug": "cscrf-sampling",
        "name": "CSCRF sampling",
        "description": "Apply the CSCRF population sampling rule.",
        "tools": [],
        "instructions": (
            "When the population is at most 25, select 100 percent. When it is "
            "larger, select at least 25 percent, rounded up. Show the population "
            "count, the sample size and the selection method. Do not drop items to "
            "look cleaner."
        ),
    },
    {
        "slug": "risk-scoring",
        "name": "Risk scoring",
        "description": "Score likelihood and impact on a 1 to 5 scale.",
        "tools": ["grc.risks.propose"],
        "instructions": (
            "Inherent score is likelihood times impact. State both factors. Do not accept the risk."
        ),
    },
    {
        "slug": "oscal-handling",
        "name": "OSCAL handling",
        "description": "Read an OSCAL catalog and map control ids without copying licensed text.",
        "tools": ["grc.controls.search"],
        "instructions": (
            "Use control ids and titles. Do not paste ISO, PCI or SOC 2 statement "
            "text into a suggestion."
        ),
    },
)

_ROUTINES: tuple[dict[str, object], ...] = (
    {
        "name": "grc-ccm",
        "agent": "control-tester",
        "cron": "0 6 * * *",
        "instructions": "Record the result. Open a finding when the test fails.",
        "delivery": [],
    },
    {
        "name": "grc-exception-expiry",
        "agent": "risk-analyst",
        "cron": "0 5 * * *",
        "instructions": "Set an exception or waiver to expired when expires_at has passed.",
        "delivery": [],
    },
    {
        "name": "grc-evidence-freshness",
        "agent": "evidence-collector",
        "cron": "0 6 * * *",
        "instructions": "Tell the control owner when an evidence link is stale.",
        "delivery": [{"type": "in_app"}],
    },
    {
        "name": "grc-regulatory-poll",
        "agent": "regulatory-watcher",
        "cron": "0 7 * * *",
        "instructions": "Fetch enabled feeds. Classify each new circular. Do not triage.",
        "delivery": [{"type": "in_app"}],
    },
    {
        "name": "grc-sla-nudge",
        "agent": "remediation-tracker",
        "cron": "0 8 * * *",
        "instructions": "Summarise open issues past due.",
        "delivery": [{"type": "in_app"}],
    },
    {
        "name": "grc-campaign-reminder",
        "agent": "access-review-coordinator",
        "cron": "0 9 * * *",
        "instructions": "Remind assignees who still have an open campaign item.",
        "delivery": [{"type": "in_app"}],
    },
    {
        "name": "grc-board-pack",
        "agent": "board-reporter",
        "cron": "0 9 1 * *",
        "instructions": "Draft the board pack. Do not send it.",
        "delivery": [{"type": "in_app", "review_before_send": True}],
    },
)


def install(store: Any, actor: Actor) -> None:
    agents = {spec["slug"]: _agent(store, actor, spec) for spec in _AGENTS}
    _skills(store, actor)
    book = RoutineBook(store)
    for spec in _ROUTINES:
        if _named(store, actor, str(spec["name"])):
            continue
        agent = agents.get(spec["agent"])
        if not isinstance(agent, dict):
            continue
        try:
            book.create(
                actor,
                {
                    "name": spec["name"],
                    "description": spec["instructions"],
                    "instructions": spec["instructions"],
                    "agent_id": str(agent["id"]),
                    "trigger": {"type": "schedule", "cron": spec["cron"], "timezone": "UTC"},
                    "delivery": spec["delivery"],
                },
            )
        except ArError:
            continue


def _agent(store: Any, actor: Actor, spec: dict[str, object]) -> dict[str, Any]:
    slug = str(spec["slug"])
    for row in store.agents.values():
        if row.get("tenant_id") == actor.tenant_id and row.get("slug") == slug:
            return cast("dict[str, Any]", row)
    definition = dict(_SHARED)
    definition["instructions"] = spec["instructions"]
    definition["tools"] = spec.get("tools") or []
    if spec.get("skills"):
        definition["skills"] = spec["skills"]
    if isinstance(spec.get("sandbox"), dict):
        definition["sandbox"] = spec["sandbox"]
    agent_id = new_id()
    now = utcnow()
    row = {
        "id": agent_id,
        "tenant_id": actor.tenant_id,
        "slug": slug,
        "name": spec["name"],
        "description": spec["description"],
        "owner_user_id": actor.user_id,
        "owner_team_id": None,
        "visibility": "tenant",
        "status": "published",
        "disabled": False,
        "risk_tier": "medium",
        "definition": definition,
        "draft_version_id": None,
        "published_version_id": None,
        "created_at": now,
        "updated_at": now,
    }
    store.agents[agent_id] = row
    return row


def _skills(store: Any, actor: Actor) -> None:
    known = {
        str(row.get("qualified_name"))
        for row in store.tool_versions.values()
        if isinstance(row, dict)
    }
    book = SkillBook(store)
    for spec in _SKILLS:
        slug = str(spec["slug"])
        if book.published_by_slug(actor.tenant_id, slug) is not None:
            continue
        raw_tools = spec.get("tools")
        names = raw_tools if isinstance(raw_tools, list) else []
        tools = [str(name) for name in names if str(name) in known]
        try:
            created = book.create(
                actor,
                {
                    "slug": slug,
                    "name": spec["name"],
                    "description": spec["description"],
                    "instructions_md": spec["instructions"],
                    "visibility": "tenant",
                    "required_tools": tools,
                },
            )
            book.publish(actor, uuid.UUID(str(created["id"])), change_note="pack")
        except ArError:
            continue


def _named(store: Any, actor: Actor, name: str) -> bool:
    return any(
        row.get("tenant_id") == actor.tenant_id and row.get("name") == name
        for row in store.routines.values()
    )
