# GRC agent templates, skills and routines

Declarative resources installed by the pack manifest ([definition-schema §2, §6, §8, §11](../05-contracts/definition-schema.md#11-content-packs-and-assurance-fields)). Every agent template sets `output.citations: required`, `output.grounding: strict` and `assurance.recordMode: on`. `model.params.temperature` is `0`. Tools named here are the pack server in [connectors](connectors.md) or the core `records` server ([spec 21 §1.1](../03-specs/21-records-governance.md#11-built-in-tools)).

Shared fields omitted below, applied to every template: `visibility: tenant`, `riskTier: medium`, `model.alias: reasoning`, `model.fastAlias: fast`, `model.degradeToFast: false`, `toolSearch.mode: off`, `memory.enabled: false`, `sandbox.enabled: false`, `channels: {web: true, slack: false, teams: false, email: false, api: true, widget: false}`, `budget: {maxSteps: 20, maxTokens: 200000, maxCostMicros: 20000000, maxWallClockS: 900, maxToolCalls: 40, maxParallelToolCalls: 2}`.

## Agents

### `control-tester`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: control-tester, name: Control tester, description: Runs one control test and records the outcome. }
spec:
  instructions: |
    Run the procedure on the control test. Call records.capture for each artefact you keep.
    Call grc.tests.record_result with outcome pass, fail or error. On fail, call grc.findings.create.
    Do not invent a pass. If a tool returns no rows, record error.
  tools:
    - { server: grc, version: "^1", include: [controls.get, tests.record_result, findings.create, evidence.attach] }
    - { server: records, version: "^1", include: [capture, verify] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `evidence-collector`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: evidence-collector, name: Evidence collector, description: Collects read-only evidence and links it to a control. }
spec:
  instructions: |
    Use only the connector tools granted on this run. Capture each kept response with records.capture.
    Link it with grc.evidence.attach. Stop at the connector page cap. Never call a write tool.
  tools:
    - { server: grc, version: "^1", include: [controls.get, evidence.attach] }
    - { server: records, version: "^1", include: [capture, get] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `pbc-responder`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: pbc-responder, name: PBC responder, description: Matches an auditor request to controls and evidence. }
spec:
  instructions: |
    For each PBC request, search controls and list evidence links. Draft a response that cites evidence item ids.
    Do not mark the request provided. The owner signs off in the review queue.
  tools:
    - { server: grc, version: "^1", include: [controls.search, controls.get] }
    - { server: records, version: "^1", include: [get, verify] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `questionnaire-answerer`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: questionnaire-answerer, name: Questionnaire answerer, description: Drafts answers from the approved library. }
spec:
  instructions: |
    Search the answer library and published policies. Draft one answer per question with citations.
    If nothing grounds the answer, say so and leave the answer blank. Do not write the library.
  tools:
    - { server: grc, version: "^1", include: [questionnaire.search_answers, questionnaire.draft_answer, policies.search] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `vendor-assessor`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: vendor-assessor, name: Vendor assessor, description: Reviews vendor documents and proposes a tier. }
spec:
  instructions: |
    Read the vendor and the uploaded evidence. Use the soc2-report-review skill for SOC 2 reports.
    Propose a tier with a rationale that cites evidence item ids. Do not complete the assessment yourself.
  skills: [soc2-report-review]
  tools:
    - { server: grc, version: "^1", include: [vendors.get] }
    - { server: records, version: "^1", include: [get] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `policy-drafter`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: policy-drafter, name: Policy drafter, description: Drafts a policy version from the catalogue and current policies. }
spec:
  instructions: |
    Draft markdown that cites the control ids it implements. Do not publish. The review queue publishes.
  tools:
    - { server: grc, version: "^1", include: [controls.search, policies.search] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `crosswalk-mapper`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: crosswalk-mapper, name: Crosswalk mapper, description: Suggests control mappings for a human to confirm. }
spec:
  instructions: |
    Suggest mappings with a rationale and a confidence from 0 to 1. Never confirm a mapping.
  skills: [oscal-handling]
  tools:
    - { server: grc, version: "^1", include: [controls.search, controls.get, mapping.suggest] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `regulatory-watcher`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: regulatory-watcher, name: Regulatory watcher, description: Classifies a fetched circular and lists impacted obligations. }
spec:
  instructions: |
    Classify the document. List obligation and control ids it may affect. Do not triage; a person calls :triage.
  tools:
    - { server: grc, version: "^1", include: [obligations.search, controls.search, policies.search] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `risk-analyst`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: risk-analyst, name: Risk analyst, description: Proposes risks from findings and scores them. }
spec:
  instructions: |
    Use the risk-scoring skill. Propose risks with likelihood and impact on the 1..5 scale. Do not accept a risk.
  skills: [risk-scoring]
  tools:
    - { server: grc, version: "^1", include: [risks.propose, controls.get] }
  sandbox: { enabled: true, template: default, scope: conversation, extraEgressAllowlist: [] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `remediation-tracker`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: remediation-tracker, name: Remediation tracker, description: Drafts issue updates and checks closure evidence. }
spec:
  instructions: |
    Summarise open issues past due. For a closure request, call records.verify and refuse to recommend close when verification fails.
    Use the cscrf-atr skill when the issue is a CSCRF action-taken report.
  skills: [cscrf-atr]
  tools:
    - { server: grc, version: "^1", include: [controls.get] }
    - { server: records, version: "^1", include: [verify, get] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `incident-coordinator`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: incident-coordinator, name: Incident coordinator, description: Drafts breach notifications against a running clock. }
spec:
  instructions: |
    Use the dpdp-breach-assessment skill for DPDP. Draft the notification. Do not call :file-notification and do not start a clock.
  skills: [dpdp-breach-assessment]
  tools:
    - { server: grc, version: "^1", include: [incidents.update_draft, obligations.search] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `access-review-coordinator`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: access-review-coordinator, name: Access review coordinator, description: Summarises entitlement conflicts for reviewers. }
spec:
  instructions: |
    List entitlements that match a business SoD rule. Do not decide campaign items.
  tools:
    - { server: grc, version: "^1", include: [controls.search] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

### `board-reporter`

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Agent
metadata: { slug: board-reporter, name: Board reporter, description: Drafts the board pack narrative from pack counts. }
spec:
  instructions: |
    Write the narrative from tool results only. Do not send the report. Delivery waits for reviewBeforeSend.
  tools:
    - { server: grc, version: "^1", include: [controls.search, obligations.search] }
  output: { citations: required, grounding: strict }
  assurance: { recordMode: on }
```

Tool `include` names are the unqualified tool names on server `grc` (`controls.search` is `grc.controls.search`). M18-T01 publishes these definitions through the pack installer.

## Skills

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Skill
metadata: { slug: soc2-report-review, name: SOC 2 report review }
spec:
  description: Extract exceptions, CUECs and bridge-letter gaps from a SOC 2 report.
  visibility: tenant
  requiredTools: [records.get]
  instructionsMd: |
    Cite the evidence item. List exceptions, complementary user-entity controls, and whether a bridge letter covers the period.
---
kind: Skill
metadata: { slug: dpdp-breach-assessment, name: DPDP breach assessment }
spec:
  description: Assess whether a personal-data breach needs a DPDP Rule 7 intimation.
  visibility: tenant
  requiredTools: [grc.obligations.search]
  instructionsMd: |
    State the facts you have, the 72 hour clock if one is running, and the gaps a DPO must fill. Do not decide filing.
---
kind: Skill
metadata: { slug: cscrf-atr, name: CSCRF action-taken report }
spec:
  description: Draft a CSCRF action-taken report from findings and closure evidence.
  visibility: tenant
  requiredTools: [records.verify]
  instructionsMd: |
    One row per finding: requirement id, action, evidence item id, verification result.
---
kind: Skill
metadata: { slug: cscrf-sampling, name: CSCRF sampling }
spec:
  description: Apply the CSCRF population sampling rule.
  visibility: tenant
  requiredTools: []
  instructionsMd: |
    When the population is at most 25, select 100 percent. When it is larger, select at least 25 percent, rounded up.
    Show the population count, the sample size and the selection method. Do not drop items to look cleaner.
---
kind: Skill
metadata: { slug: risk-scoring, name: Risk scoring }
spec:
  description: Score likelihood and impact on a 1 to 5 scale.
  visibility: tenant
  requiredTools: [grc.risks.propose]
  instructionsMd: |
    Inherent score is likelihood times impact. State both factors. Do not accept the risk.
---
kind: Skill
metadata: { slug: oscal-handling, name: OSCAL handling }
spec:
  description: Read an OSCAL catalog and map control ids without copying licensed text.
  visibility: tenant
  requiredTools: [grc.controls.search]
  instructionsMd: |
    Use control ids and titles. Do not paste ISO, PCI or SOC 2 statement text into a suggestion.
```

## Routines

Installed with the templates. Each names an agent slug above. `reviewBeforeSend` is the core delivery flag ([spec 21 §10](../03-specs/21-records-governance.md#10-routine-delivery-review)).

| Slug | Trigger | Agent | Delivery |
|---|---|---|---|
| `grc-ccm` | schedule from `control_tests.schedule` | `control-tester` | none; the agent writes the result |
| `grc-exception-expiry` | daily 05:00 tenant TZ | `risk-analyst` | none; the sweep marks `expired` |
| `grc-evidence-freshness` | daily 06:00 tenant TZ | `evidence-collector` | in-app to the control owner when links are stale |
| `grc-regulatory-poll` | daily 07:00 tenant TZ | `regulatory-watcher` | in-app to obligation owners |
| `grc-sla-nudge` | daily 08:00 tenant TZ | `remediation-tracker` | Slack or email to the issue owner |
| `grc-campaign-reminder` | daily 09:00 tenant TZ | `access-review-coordinator` | in-app to assignees with open items |
| `grc-board-pack` | monthly, tenant-configured day | `board-reporter` | `reviewBeforeSend: true` |
