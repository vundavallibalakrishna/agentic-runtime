# PRD — GRC solution pack

Stories for the pack only. Core assurance stories are [PRD 15](../01-prd/15-records-governance.md). Personas: [personas](../00-overview/personas.md). Normative behaviour: the other files in this folder. Plan: [M16](../09-plan/M16-grc-foundation.md)–[M19](../09-plan/M19-grc-audit-reporting.md).

### US-GRC-01 · Continuous control monitoring (P0)
As a **control owner**, I want scheduled tests to collect evidence and open a finding when a control fails.
- A `control_tests` row with a schedule starts a routine that calls read-only connector tools, stores evidence through `records.capture`, writes `test_results`, and calls `grc.findings.create` (W2) on `fail`.
- Spec: [domain-model](domain-model.md), [connectors](connectors.md). Plan: M17-T05, M18 is not required for the collector path.

### US-GRC-02 · Evidence collection (P0)
As a **control owner**, I want cloud, identity, ticketing and code evidence attached to controls with a freshness date.
- P1 connectors in [connectors](connectors.md) capture hashed evidence. `POST /api/v1/ext/grc/evidence-links` requires `evidence:read` on the core item. Stale links are listed with `stale=true`.
- Spec: connectors, [api](api.md). Plan: M16-T04, M17-T01..T04.

### US-GRC-03 · PBC and auditor portal (P0)
As an **external auditor**, I want a time-boxed portal of the requests I was granted, and nothing else.
- `POST /api/v1/ext/grc/pbc-lists:import` creates requests. A guest with portal `auditor` sees only `pack_record_ids` in the grant. Responses require core sign-off before status `provided`.
- Spec: api, [spec 21 §4](../03-specs/21-records-governance.md#4-guest-principals). Plan: M19-T01.

### US-GRC-04 · Questionnaire answering (P0)
As a **control owner**, I want drafted answers from the approved library, each reviewed before export.
- `grc.questionnaire.draft_answer` cites library rows or policies. Export returns 409 `review_required` until every exported answer is `approved`.
- Spec: api, [agent-templates](agent-templates.md). Plan: M18-T01.

### US-GRC-05 · Vendor risk (P0)
As a **control owner**, I want vendor intake, a questionnaire, document review and a tier.
- Vendors and assessments are pack rows. The vendor guest portal is portal `vendor`. The SOC 2 skill extracts exceptions and CUECs into the assessment.
- Spec: api, agent-templates. Plan: M18-T02.

### US-GRC-06 · Policy lifecycle (P0)
As a **tenant admin**, I want a policy drafted, reviewed, published and acknowledged.
- Publish is allowed only after the review item on that version is `signed`. Acknowledgement campaigns write `grc.policy.acknowledged`.
- Spec: api. Plan: M18-T03.

### US-GRC-07 · Crosswalks (P0)
As a **control owner**, I want suggested mappings between frameworks that a second person confirms.
- Suggestions are `status=suggested`. `:confirm` refuses when the confirmer is `suggested_by`.
- Spec: [framework-catalogues](framework-catalogues.md), api. Plan: M16-T03, M18 is the mapper agent.

### US-GRC-08 · Regulatory change (P0)
As a **control owner**, I want new circulars triaged against obligations and controls.
- Feeds in [domain-model](domain-model.md) are polled. Triage audits `grc.regulatory_change.triaged`. The eval set includes Hindi circulars.
- Spec: domain-model, agent-templates. Plan: M18-T05.

### US-GRC-09 · Risk register (P0)
As a **control owner**, I want proposed risks scored and accepted only by sign-off.
- Score is `likelihood * impact` on a 1..5 scale. `:accept` opens a review item. `grc.risk.accepted` is written when that item is `signed`.
- Spec: api. Plan: M18-T04.

### US-GRC-10 · Findings and remediation (P0)
As a **control owner**, I want findings synced to Jira or ServiceNow and closed only with verified evidence.
- `:close` returns 409 `closure_evidence_required` when the evidence item is missing or fails `records.verify`.
- Spec: api, connectors. Plan: M17-T04, M17-T05.

### US-GRC-11 · Breach clocks (P0)
As a **tenant admin**, I want CERT-In (6 h), DPDP (72 h) and GDPR (72 h) clocks with a signed filing record.
- `:start-clock` is idempotent per regime. `:file-notification` records the filing only after sign-off. Targeted before 13 May 2027.
- Spec: api. Plan: M18-T06.

### US-GRC-12 · Access reviews (P0)
As an **approver**, I want entitlement campaigns and business SoD conflicts that are separate from platform SoD.
- `grc.entitlements` and `grc.sod_rules` are pack tables. Decisions go through core sign-off. Platform `sod_constraints` are unchanged.
- Spec: api, domain-model. Plan: M19-T02.

### US-GRC-13 · Attestations (P0)
As a **control owner**, I want a campaign whose completion is an immutable sign-off.
- Campaign kind `attestation` writes a core sign-off bound to the statement hash.
- Spec: api. Plan: M19-T03.

### US-GRC-14 · AI inventory beyond this platform (P1)
As an **auditor**, I want external AI systems recorded beside this platform's agent cards.
- External systems are pack assets with `kind=ai_system`. This platform's agents stay in core `agent_cards` ([spec 21 §3](../03-specs/21-records-governance.md#3-ai-governance-register)).
- Spec: domain-model. Plan: M16-T02 (asset row), M19-T04 (report includes both).

### US-GRC-15 · Board pack (P1)
As a **tenant admin**, I want a scheduled board report that is reviewed before it is sent.
- Template `board_pack` renders through the core binder API. Routine delivery uses `reviewBeforeSend` ([spec 21 §10](../03-specs/21-records-governance.md#10-routine-delivery-review)).
- Spec: api. Plan: M19-T04.
