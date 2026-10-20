# M18 — GRC agents, skills and workflows

Goal: the high-value GRC workflows run as pack agent templates on core sign-off, grounding and run records.

Exit criteria: a questionnaire export is blocked until each answer is approved; a risk acceptance stays proposed until sign-off; a DPDP clock can be started and a filing recorded only after sign-off.

M18-T06 is targeted before 13 May 2027, when DPDP Rule 7 applies.

---

### M18-T01 · Questionnaire answerer and answer library
- **Depends on:** M16-T05, M5-T08, M7-T11
- **Areas:** `packs/grc/src/ar_pack_grc/questionnaires.py`, templates `questionnaire-answerer`
- **Spec:** [api](../10-grc-pack/api.md), [agent-templates](../10-grc-pack/agent-templates.md), [prd](../10-grc-pack/prd.md)
- **Do:** Answer-library and questionnaire endpoints. Tools `grc.questionnaire.search_answers` (R0) and `grc.questionnaire.draft_answer` (R1). Publish the agent templates whose behaviour exists: `questionnaire-answerer`, and the shared assurance fields on every template in agent-templates.md. Export returns 409 `review_required` when any exported answer is not `approved`. Bulk review uses core `:bulk-decide`.
- **Done when:** an ungrounded strict draft contains no factual sentence without a citation; export of an unapproved answer is refused.
- **Tests:** library expiry excluded from search; export guard; bulk review of 100 answers.

### M18-T02 · Vendor risk
- **Depends on:** M18-T01, M14-T11
- **Areas:** `packs/grc/src/ar_pack_grc/vendors.py`, skill `soc2-report-review`, template `vendor-assessor`, guest portal `vendor`
- **Spec:** [api](../10-grc-pack/api.md), [agent-templates](../10-grc-pack/agent-templates.md)
- **Do:** Vendor and assessment endpoints. Portal `vendor` registered for guest grants. The SOC 2 skill extracts exceptions, CUECs and bridge-letter gaps. `:score` audits `grc.assessment.completed`.
- **Done when:** a vendor guest sees only granted assessments; a member without `grc.vendors:read` does not.
- **Tests:** guest scope; skill fixture on a sample report; tier stored on the assessment.

### M18-T03 · Policy lifecycle
- **Depends on:** M16-T02, M5-T08
- **Areas:** `packs/grc/src/ar_pack_grc/policies.py`, template `policy-drafter`
- **Spec:** [api](../10-grc-pack/api.md)
- **Do:** Policy and version endpoints. `:publish` is allowed only when the review item for that version is `signed`. Acknowledgement campaigns are created here and completed in M19-T03. Audit `grc.policy.published`.
- **Done when:** publish before sign-off returns 409; a signed version publishes once.
- **Tests:** sign-off gate; version hash change supersedes the review item.

### M18-T04 · Risk register
- **Depends on:** M16-T05, M5-T08
- **Areas:** `packs/grc/src/ar_pack_grc/risks.py`, skill `risk-scoring`, template `risk-analyst`
- **Spec:** [api](../10-grc-pack/api.md), [domain-model](../10-grc-pack/domain-model.md)
- **Do:** Asset, risk, assessment and treatment endpoints. Tool `grc.risks.propose` (W1). Score is `likelihood * impact`. `:accept` opens a review item. Audit `grc.risk.accepted` when that item becomes `signed`, not when `:accept` is called.
- **Done when:** a score change inserts a new assessment row; acceptance without sign-off leaves status `proposed`.
- **Tests:** score history; sign-off transition; audit timing.

### M18-T05 · Regulatory change watcher
- **Depends on:** M16-T02
- **Areas:** `packs/grc/src/ar_pack_grc/regulatory.py`, template `regulatory-watcher`, routine `grc-regulatory-poll`, skill `cscrf-sampling` (published here so M19 and the ATR skill can use the sampling rule)
- **Spec:** [domain-model](../10-grc-pack/domain-model.md), [agent-templates](../10-grc-pack/agent-templates.md)
- **Do:** Feed and regulatory-change endpoints. Seed the feeds from the domain model. The watcher stores fetched pages as knowledge documents in a pack-owned collection and as `grc.regulatory_changes`. It stops at `robots.txt`. Triage audits `grc.regulatory_change.triaged`. Eval cases include Hindi circular classification. Publish skill `cscrf-sampling`.
- **Done when:** a fixture circular becomes one change row and a knowledge document; triage links the obligation ids in the body.
- **Tests:** SSRF refusal on a private feed URL; Hindi fixture; robots refusal.

### M18-T06 · Incident and breach clocks
- **Depends on:** M14-T09, M5-T08, M18-T05
- **Areas:** `packs/grc/src/ar_pack_grc/incidents.py`, template `incident-coordinator`, skill `dpdp-breach-assessment`
- **Spec:** [api](../10-grc-pack/api.md), [prd](../10-grc-pack/prd.md)
- **Do:** Incident endpoints. `:start-clock` starts a Temporal timer of 6 h for `cert_in` and 72 h for `dpdp` and `gdpr`, idempotent per regime. Tool `grc.incidents.update_draft` (W2). `:file-notification` records the filing only after the review item is `signed`, and audits `grc.incident.notified`. Opening an incident can attach a legal hold through the core API; it does not create one silently.
- **Done when:** a second start returns the existing clock; filing before sign-off does not audit `grc.incident.notified`.
- **Tests:** timer durations; idempotent start; sign-off gate. Target this task before 13 May 2027.

### M18-T07 · Exceptions, waivers and compensating controls
- **Depends on:** M16-T03, M5-T08
- **Areas:** `packs/grc/src/ar_pack_grc/exceptions.py`
- **Spec:** [use-cases U18–U19](../10-grc-pack/use-cases.md)
- **Do:** `grc.exceptions`. Kind `exception` or `waiver`. A waiver requires `compensating_control_id`. Status becomes `signed` only after core sign-off. A daily routine sets `expired` when `expires_at` has passed. Endpoints in [api](../10-grc-pack/api.md).
- **Done when:** a waiver without a compensating control returns 422; an expired exception is ignored by the control test.
- **Tests:** sign-off gate; expiry sweep.

### M18-T08 · Ethics cases
- **Depends on:** M16-T01, M14-T09
- **Areas:** `packs/grc/src/ar_pack_grc/ethics.py`
- **Spec:** [use-cases U24](../10-grc-pack/use-cases.md)
- **Do:** `grc.ethics_cases`. `restricted=true` rows are readable only with `grc.ethics:manage`. Opening a case can attach a core legal hold; it does not create one silently. No hotline and no external intake portal in this task.
- **Done when:** a tenant auditor without `grc.ethics:manage` receives 404 for the case.
- **Tests:** permission hide; audit `grc.ethics.opened`.
