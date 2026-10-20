> **Placement.** This is the approved analysis (2026-10-20), stored at `docs/grc-gap-analysis.md`. Links below are relative to `docs/` and resolve from this file. The product owner approved every plan change in §7. Open-question ids proposed as OQ-21..OQ-25 in §7.3 were already assigned on `main`; the approved questions are recorded as [OQ-25](open-questions.md) through [OQ-29](open-questions.md).

# Agentic Runtime — GRC use-case fit and gap analysis

- Date: 2026-10-20 (IST). Scope: the spec set in `agentic_runtime/` (117 files, 16 milestones, 130 tasks). No specs were changed for this analysis.
- Audience: TalentFino product and engineering. Target buyers: GRC teams (CISO office, compliance, internal audit, risk, privacy, third-party risk) running the platform in-house (single-tenant) or as SaaS.
- Paths below are relative to `agentic_runtime/docs/`.

## 0. Summary

**Fit.** The core platform covers the plumbing GRC agents need well:
- Durable runs with human approvals, OPA policies and risk classes ([spec 09](03-specs/09-policy-approvals.md)).
- A hash-chained, append-only audit log with Object Lock archive ([audit §1](06-security/audit.md#1-properties)).
- ACL-aware hybrid retrieval with citations ([spec 10](03-specs/10-knowledge.md)).
- Routines for continuous monitoring ([spec 15](03-specs/15-routines-triggers.md)).
- Sandboxes for deterministic calculations and spreadsheet work ([spec 12](03-specs/12-sandbox-manager.md)).
- MCP / OpenAPI connectors ([spec 08](03-specs/08-tool-registry-mcp.md)).
- Evals with publish gates ([spec 18 §4](03-specs/18-observability-eval.md#4-evaluation)).
- DPDP data-principal tooling ([data-protection](06-security/data-protection.md)).

**What GRC buyers will find missing** falls into three groups:
1. **Records and assurance:**
   - an immutable evidence store with chain of custody;
   - legal hold beyond conversations and files;
   - reproducible "run records" that an auditor can re-perform;
   - claim-level grounding.
2. **Governance workflow:**
   - sign-off/attestation on outputs, not only on tool calls;
   - segregation of duties (SoD);
   - external auditor and vendor access;
   - an AI governance register.
3. **Domain:** no GRC data model (frameworks, controls, risks, evidence, findings, vendors), no packaged evidence connectors (cloud, IdP, ITSM), and no auditor-grade reporting.

**Recommendation.**
- Add about 11 tasks to existing core milestones (M3, M5, M7, M13, M14) for capabilities that are generic: any regulated buyer needs them. No change to M1.
- Build a separate **GRC solution pack** as four new milestones (M16–M19, about 23 tasks): domain schema, frameworks and crosswalks, evidence connectors as MCP servers, agent templates, skills and routines, auditor/vendor portals and reports.
- Add a small core "pack extension points" task so the pack never forks the core.

## 1. Regulatory and practice context (checked 2026-10-20)

| Regime | Status relevant to product design |
|---|---|
| India DPDP Act 2023 + DPDP Rules 2025 | Rules notified 13 Nov 2025 with phased commencement: Rule 4 from 13 Nov 2026; most obligations, including **Rule 7 breach intimation (Board within 72 h, data principals without delay)**, from 13 May 2027. Breach workflow and consent/notice evidence become high-demand in 2027. |
| SEBI CSCRF (Aug 2024; extensions 2025) | Annual/half-yearly cyber audits and VAPT with action-taken reports (ATRs); FY 2025-26 cycle due Jun–Nov 2026. 100 % of critical and 25 % of non-critical systems audited, with the sampling rationale documented. Evidence sampling and ATR tracking are concrete agent jobs. |
| RBI (IT Governance Master Direction 2023; cyber directions; FREE-AI framework Aug 2025) | Board-approved AI policy, AI lifecycle governance, audits and incident reporting recommended for regulated entities. Buyers will ask how the platform's own AI is governed. |
| CERT-In Directions 2022 | 6-hour incident reporting and 180-day log retention in India. Drives incident-workflow timers and log retention. |
| EU AI Act | Art. 50 transparency obligations apply from 2 Aug 2026; Annex III high-risk obligations from 2 Dec 2027 (after the Digital Omnibus). Logging, traceability and human oversight are explicit requirements. |
| ISO/IEC 42001, NIST AI RMF | Organisational AI management system and risk framework; ISO 42001 alone does not satisfy AI Act conformity. Buyers expect an AI system inventory, impact assessments and monitoring evidence. |
| ISO 27001:2022, SOC 2, NIST CSF 2.0, PCI DSS v4.0.1, GDPR | Core control frameworks. **Licensing:** ISO and some questionnaire standards (e.g. the Shared Assessments SIG) are copyrighted, so the pack ships control IDs, titles where licensed, and import of customer-licensed text. NIST (OSCAL catalogues) and the CSA CAIQ are freely usable. |

Current practice in GRC tooling is continuous control monitoring through API-based evidence collection, AI-assisted questionnaire answering from an approved-answer library, and framework crosswalks through a common control set. Machine-readable catalogues use NIST OSCAL. Differentiators for an in-house runtime are data residency, ACL-respecting retrieval, auditable AI and human sign-off.

## 2. Highest-value GRC agent use cases

Value: H = strong buyer pull and repeatable ROI; M = valuable but narrower. "Pattern" is how the agent works on this platform.

| # | Use case | Value | Pattern |
|---|---|---|---|
| U1 | Continuous control monitoring (CCM) and automated control testing | H | Routine (schedule) → read-only evidence tools → sandbox test script → pass/fail with evidence → finding on fail |
| U2 | Evidence collection from AWS/Azure/GCP, Okta/Entra, Jira/ServiceNow, GitHub/GitLab, HRIS, EDR/MDM | H | Collector agent with R0/R1 tools; evidence items hashed and stored; mapped to controls |
| U3 | Audit preparation and auditor request (PBC list) handling | H | Ingest the PBC list (XLSX) → match requests to controls/evidence → draft responses → owner sign-off → auditor portal |
| U4 | Security/customer questionnaire answering (CAIQ, SIG-style, custom XLSX/portal) | H | Knowledge retrieval over the approved-answer library and policies → drafted answers with citations → reviewer approval per answer → export in the original format |
| U5 | Third-party/vendor risk: intake, questionnaires, due-diligence document review (SOC 2 reports, ISO certificates, pen-test summaries), risk tiering | H | Vendor intake routine → send questionnaire → analyse returned docs (bridge letters, SOC 2 exceptions, CUECs) → risk score → follow-ups |
| U6 | Policy drafting, review and policy-to-control mapping | H | Drafting agent using the framework catalogue and existing policies → redline diff → approval and publication with versioning |
| U7 | Framework crosswalks and gap assessments (ISO 27001 ↔ SOC 2 ↔ NIST CSF ↔ PCI DSS ↔ DPDP ↔ RBI/SEBI CSCRF) | H | Common-control mapping agent with human confirmation; gap report per framework |
| U8 | Regulatory change monitoring and impact analysis (RBI, SEBI, CERT-In, MeitY/DPB, EU) | H | Routine polls feeds/sites → classify relevance → impact analysis against obligations/controls/policies → tasks for owners |
| U9 | Risk register maintenance and risk scoring | M-H | Agent proposes risks from findings/incidents/changes; deterministic scoring (likelihood × impact, or quantitative FAIR-style models in the sandbox); owner acceptance |
| U10 | Issue/finding and remediation tracking (incl. SEBI ATRs) | H | Findings synced with Jira/ServiceNow; SLA routines; nudges in Slack/Teams/email; closure evidence verified before close |
| U11 | Incident and breach-notification workflow (DPDP Rule 7, CERT-In 6 h, GDPR 72 h, sector regulators) | H | Incident intake → clock start → applicability decision support → draft notifications → legal/DPO sign-off → filing record |
| U12 | User access reviews and attestations | H | Pull entitlements from IdP/apps → reviewer campaigns → revoke tickets → evidence of completion; SoD conflict detection |
| U13 | Control owner attestations and periodic certifications (policy acknowledgement, quarterly control self-assessment) | M | Campaign routine → per-owner questionnaire → sign-off → evidence |
| U14 | AI governance for the customer's own AI systems (ISO 42001 / EU AI Act / NIST AI RMF): AI inventory, impact assessments, model monitoring evidence | M-H | Inventory agent + assessment templates; evidence from model registries; this platform's own agents are the first inventory entries |
| U15 | Board/committee reporting (risk posture, compliance status, KRIs) | M | Scheduled reporting agent over the GRC data → deck/PDF artifact → review → distribution |

## 3. Coverage per use case

Legend: ✅ covered, 🟡 partial, ❌ missing. "Core" items are reusable platform features; "Pack" items are GRC-specific.

| # | Covered by existing specs | Missing |
|---|---|---|
| U1 CCM | ✅ Schedules/polling routines ([spec 15 §2, §6](03-specs/15-routines-triggers.md#2-triggers)); ✅ sandbox code for test logic ([spec 12](03-specs/12-sandbox-manager.md)); ✅ OpenAPI/SQL connectors ([spec 08 §10–11](03-specs/08-tool-registry-mcp.md#10-mcp-sql-connector-runtime-connectorsmcp_sql-port-8010)); ✅ delivery to channels ([spec 15 §4](03-specs/15-routines-triggers.md#4-delivery-phase-in-agentrunworkflow-for-triggerroutine)) | ❌ Control/test definitions and results model (Pack); ❌ evidence store with hashes (Core); 🟡 deterministic test re-performance: no "run record" binding test code + inputs + outputs (Core); ❌ prebuilt cloud/IdP collectors (Pack) |
| U2 Evidence collection | ✅ MCP host, OAuth credential providers, delegated credentials ([spec 03](03-specs/03-secrets-credentials.md), [spec 08](03-specs/08-tool-registry-mcp.md)); ✅ R0/R1 risk classes allow unattended reads ([spec 09 §2](03-specs/09-policy-approvals.md#2-defaults-by-risk-class-no-rule-matched)); ✅ files/artifacts ([spec 13](03-specs/13-files-artifacts.md)) | ❌ Evidence item type (immutable object + content hash + source + collection method + timestamp + collector identity + chain of custody) (Core); ❌ connector catalogue: AWS, Azure, GCP, Okta, Entra ID, Google Workspace, Jira, ServiceNow, GitHub/GitLab, CrowdStrike/Defender, Intune/Jamf, HRIS (Pack); ❌ screenshot-style evidence with provenance from `browser.*` (Core: browser screenshot exists as an event, not as evidence) |
| U3 Audit prep / PBC | ✅ XLSX parsing in ingestion and sandbox; ✅ knowledge with citations; ✅ approvals | ❌ Request/response object model with status and owners (Pack); ❌ external auditor access, time-boxed and scoped (Core identity primitive + Pack portal); ❌ sign-off on responses (Core); ❌ auditor binder export (Core export + Pack templates) |
| U4 Questionnaires | ✅ Retrieval with ACLs and citations ([spec 10 §6.4](03-specs/10-knowledge.md#64-retrieval-pipeline-ar_domainknowledgeretrieval-backend-independent)); ✅ sandbox for XLSX round trip; ✅ memory for preferences ([spec 11](03-specs/11-memory.md)) | ❌ Approved-answer library with owners, expiry and versioning (Pack); 🟡 claim-level citation enforcement and "insufficient evidence" behaviour beyond the answerability threshold (Core); ❌ bulk review UI (answer-by-answer accept/edit/reject) (Core: generic review queue; Pack: questionnaire view) |
| U5 Vendor risk | ✅ Document ingestion (PDF/Office/OCR); ✅ routines; ✅ email channel for notifications ([spec 16](03-specs/16-channels.md)) | ❌ Vendor, engagement, assessment, tiering model (Pack); ❌ external respondent access (vendors cannot log in: [scope non-goals](00-overview/scope.md#non-goals-v1)) (Core guest principal + Pack portal); ❌ SOC 2 report analysis skill (exceptions, CUECs, bridge letters) (Pack skill) |
| U6 Policy drafting/mapping | ✅ Agents, skills ([spec 14](03-specs/14-skills.md)), knowledge, artifacts; ✅ approvals for publishing to SharePoint/Confluence as W2 tools | ❌ Policy document lifecycle (draft → review → approve → publish → acknowledge, version history, owner, review date) (Pack, built on Core sign-off); 🟡 redline/diff artifacts (Core artifact viewer has no document diff) |
| U7 Crosswalks | ✅ Retrieval + reasoning; ✅ sandbox for matrix generation | ❌ Framework catalogue model with OSCAL import/export, common control set and mappings with confidence and human confirmation (Pack); ❌ licensed-content handling (Pack) |
| U8 Regulatory change | ✅ `web` knowledge source + schedules ([spec 10 §5.2](03-specs/10-knowledge.md#52-built-in-connectors)); ✅ routine polling; ✅ `web.fetch` with allowlist | ❌ Obligation register and regulator feed catalogue (RBI, SEBI, CERT-In, MeitY, DPB, EUR-Lex) (Pack); ❌ change → obligation → control impact links (Pack); ❌ Hindi/regional-language circular handling evals (Pack eval suite) |
| U9 Risk register | ✅ Sandbox for deterministic scoring; ✅ approvals | ❌ Risk, asset, threat, KRI, treatment and acceptance model with scoring methodology config (Pack); ❌ risk acceptance sign-off with expiry (Core sign-off) |
| U10 Issues/remediation | ✅ Jira/ServiceNow via MCP/OpenAPI as W2 tools with approvals; ✅ routines for SLA nudges; ✅ notifications ([spec 20](03-specs/20-notifications-events.md)) | ❌ Finding model with severity, owner, due date and links to control/evidence (Pack); ❌ bi-directional ITSM sync (Pack connector); ❌ closure-evidence verification before close (Pack agent + Core evidence) |
| U11 Incident/breach notification | ✅ Webhook routines (intake), approvals, channels | ❌ Incident case model with regulatory clocks (6 h / 72 h) and escalation timers (Pack, Temporal timers); ❌ notification templates per regime (Pack); ❌ legal hold on all related records (Core); ❌ break-glass-friendly incident roles (Pack + Core roles) |
| U12 Access reviews | ✅ SCIM/IdP integration for the platform's own users ([spec 02](03-specs/02-identity-tenancy.md)) | ❌ Entitlement ingestion from target apps (Pack connectors); ❌ campaign/reviewer decision model (Pack, on Core sign-off); ❌ SoD rule engine for business roles (Pack; Core SoD covers platform actions only) |
| U13 Attestations | ✅ Routines + channels + approvals buttons in Slack/Teams | ❌ Attestation campaign and immutable attestation record with signer identity, step-up and statement text hash (Core sign-off + Pack campaigns) |
| U14 AI governance | ✅ Model registry, aliases, kill switches ([spec 04](03-specs/04-model-gateway.md)); ✅ evals, guardrails, audit; ✅ agent versions immutable when published ([spec 05](03-specs/05-agent-registry.md)) | ❌ AI system register / agent "model cards" (purpose, risk tier, data used, human oversight, eval evidence) (Core: the platform must govern its own agents; Pack: register for external AI systems); ❌ impact assessment templates (Pack) |
| U15 Board reporting | ✅ Usage/observability reporting; ✅ artifacts (PPTX/PDF via sandbox) | ❌ GRC metrics/KRI data model and report templates (Pack); 🟡 scheduled report with review before distribution (Core: routine delivery has no review step) |

## 4. Platform-level gaps for GRC buyers (ranked)

Ranked by deal impact (would an auditor or GRC buyer reject the platform without it?) and by how hard it is to retrofit later.

| Rank | Gap | What exists today | What is missing | Where |
|---|---|---|---|---|
| 1 | **Evidence vault with integrity and chain of custody** | Hash-chained audit (no content); files with retention; Object Lock bucket for audit archives ([spec 17 §1.4](03-specs/17-audit-usage-metering.md#14-auditexportworkflow)) | Immutable evidence objects (sha256 at capture, WORM storage class, optional RFC 3161 trusted timestamp, signature by the collecting service key), provenance (source system, query/API call, collector run/tool call ids, actor), custody log (every access/export audited and linked), retention class and legal hold, verification endpoint and export manifest | **Core** (generic "records" module); Pack maps evidence to controls |
| 2 | **Reproducible, explainable run records** | Temporal determinism for workflow code ([spec 07 §2.1](03-specs/07-agent-runtime.md#21-loop-normative-pseudocode)); `run_steps` with model id and tokens; `run_events`; content capture off by default in SaaS ([spec 18 §1](03-specs/18-observability-eval.md#1-telemetry-architecture)) | Per-agent "record mode" that stores a sealed **run record**: agent version, prompt template hashes, model id + revision/weights digest, sampling params (temperature 0, seed where supported), retrieved chunk ids + `index_version`, every tool call's arguments and results (encrypted, evidence-grade), outputs, approvals. **Re-performance**: replay with recorded tool results and a pinned model, reporting divergence. Honest positioning: LLM output is not bit-for-bit reproducible; the evidence is the recorded inputs/outputs plus deterministic code for the test logic. | **Core** |
| 3 | **Sign-off / attestation on outputs and SoD** | Approvals bind to tool-call args hash with four-eyes and step-up ([spec 09 §5](03-specs/09-policy-approvals.md#5-approvals-api), [ADR-0015](02-architecture/adr/ADR-0015-approval-args-hash.md)) | Generic **review & sign-off** on artifacts/records (statement text, content hash, signer, role, step-up, comments, multi-level chains, delegation, expiry, re-sign on change); review queues and bulk review; **SoD constraints**: preparer ≠ reviewer ≠ approver, conflicting-role pairs, the agent's owner cannot approve its own outputs, no self-approval through standing approvals | **Core** |
| 4 | **GRC domain data model** | None (generic only) | Frameworks, requirements, common controls, mappings, control tests, evidence links, risks, assets, vendors, assessments, findings, issues, policies, obligations, incidents, campaigns. Exposed to agents as tools via an MCP server, plus API and UI | **Pack** (needs Core pack extension points) |
| 5 | **External principals (auditors, vendors)** | Employees and service accounts only; anonymous access is a non-goal ([scope](00-overview/scope.md#non-goals-v1), OQ-02) | Guest principal type: invited by email, IdP-less login (magic link + TOTP) or federated, time-boxed, scoped to specific records/portals, no agent/tool access by default, every access audited, watermarking on downloads | **Core** primitive; Pack portals |
| 6 | **Legal hold and records retention beyond conversations/files** | `retention_class='legal_hold'` on conversations; file hold ([spec 17 §3](03-specs/17-audit-usage-metering.md#3-retention-retentionsweepworkflow)) | Hold objects (matter, custodian, scope query, start/release, approver) applying to conversations, runs, run records, evidence, documents, audit archive and memory; retention schedules per record class (e.g. 7–10 years for audit evidence, 180 days CERT-In logs); disposition certificates | **Core** |
| 7 | **AI governance of the platform itself (ISO 42001 / AI Act / NIST AI RMF / RBI FREE-AI)** | Model registry, evals, guardrails, kill switches, audit | AI system register with an "agent card" per agent version (intended use, risk tier, data categories, oversight mode, eval results, known limitations, owner, review date); change log tied to publish; human-oversight evidence (approval rates, overrides); AI incident log; export as AIMS evidence | **Core** (agent card + register); Pack adds assessments for external AI systems |
| 8 | **Claim-level grounding and explainability** | Knowledge citations, answerability threshold, citation validation ([spec 07](03-specs/07-agent-runtime.md), M7-T07) | Agent setting `grounding: strict` (every factual sentence must cite a knowledge chunk, evidence item or tool result, else it is removed or flagged); citations to tool results/evidence items, not only URLs; a groundedness grader as a publish gate; a "why" panel showing sources, tools and approvals per answer | **Core** |
| 9 | **Auditor-grade reporting and export** | Audit export JSONL/CSV with verification; conversation export | Report/binder builder: selected records + evidence + sign-offs + audit excerpts → PDF/XLSX/ZIP with a manifest of hashes and a verification script; scheduled reports with a review step before distribution | **Core** export engine; Pack templates (SOC 2 PBC binder, ISO SoA, CSCRF compliance formats, DPDP breach report) |
| 10 | **Connectors** | Remote MCP, OpenAPI-to-MCP, SQL connector, knowledge sources (SharePoint, Confluence, Drive, S3, web, DB) | Curated read-only evidence MCP servers and ITSM sync (§5) | **Pack** |
| 11 | **Data classification depth** | Four-level classification on documents, tools, conversations and sandboxes; clearance attribute; PII recognisers incl. Indian IDs ([data-protection §5](06-security/data-protection.md)) | Classification labels mapped to customer schemes (e.g. MIP labels); classification-driven routing (restricted → on-prem model only); evidence redaction profiles for auditor exports | Core (small) |
| 12 | **Hosting assurances buyers will ask about** | Single-tenant, air-gapped, company-hosted models ([deployment-modes](00-overview/deployment-modes.md)) | A documented control mapping of the platform itself to ISO 27001 / SOC 2 / CSCRF (the "platform trust pack"): a docs deliverable, not code | Core docs |

## 5. Connectors needed (GRC pack)

All delivered as MCP servers registered through the normal tool lifecycle ([spec 08 §2](03-specs/08-tool-registry-mcp.md#2-lifecycle)). Read tools are R0/R1 (unattended in routines); write tools are W2 (approval).

| Priority | Systems | Typical evidence / actions |
|---|---|---|
| P1 | AWS (Config, IAM, CloudTrail, Security Hub), Azure (Policy, Entra ID, Defender for Cloud), GCP (SCC, IAM) | Config snapshots, IAM users/MFA, logging enabled, encryption, public exposure |
| P1 | Okta, Microsoft Entra ID, Google Workspace | Users, MFA, admin roles, deprovisioning timeliness, entitlements for access reviews |
| P1 | Jira, ServiceNow (ITSM/GRC tables) | Change tickets, incidents, findings sync (W2 create/update) |
| P1 | GitHub/GitLab/Azure DevOps | Branch protection, PR reviews, CI scans, secrets scanning |
| P2 | CrowdStrike/Microsoft Defender, Intune/Jamf, vulnerability scanners (Tenable/Qualys/OpenVAS) | Endpoint coverage, encryption, patch SLAs, vuln aging |
| P2 | HRIS (Darwinbox, Keka, Workday, SuccessFactors) | Joiners/movers/leavers, training completion, background checks |
| P2 | SIEM/log platforms (Wazuh, Elastic, Splunk-compatible APIs) | Log retention, alert handling evidence |
| P3 | Regulator feeds: RBI, SEBI, CERT-In, MeitY/DPB, IRDAI, EUR-Lex | Circulars and notifications (knowledge `web` source + parsers) |
| P3 | E-signature / DMS | Signed policies and attestations import |

## 6. Recommendation: core versus GRC solution pack

### 6.1 Principles

1. Put a capability in **core** if any regulated buyer needs it (records integrity, reproducibility, sign-off, SoD, guest access, legal hold, AI governance of the platform's own agents, grounding, export). These strengthen 1.0 for all segments.
2. Put it in the **pack** if it encodes GRC domain semantics (frameworks, controls, risks, vendors, campaigns, regulatory content), GRC connectors, prompts, skills and templates.
3. The pack uses only public core extension points: bundles, MCP tools, skills, routines, API plugin router, pack schema, web route group, permissions and audit registration. No forks and no core table changes.

### 6.2 GRC pack shape (`packs/grc`, package `ar_pack_grc`)

| Component | Content |
|---|---|
| Domain schema | Postgres schema `grc` with its own Alembic environment (version table `grc_alembic_version`) and RLS via the core helper. Tables: `frameworks`, `requirements`, `controls`, `control_mappings`, `control_tests`, `test_results`, `evidence_links` (→ core evidence), `risks`, `risk_assessments`, `treatments`, `assets`, `vendors`, `vendor_assessments`, `findings`, `issues`, `policies`, `policy_versions`, `obligations`, `regulatory_changes`, `incidents`, `campaigns`, `campaign_items`, `answer_library` |
| Content | OSCAL importers; NIST CSF 2.0, NIST 800-53, CSA CCM/CAIQ, DPDP Act/Rules, CERT-In, RBI/SEBI CSCRF obligation catalogues; ISO 27001 / SOC 2 / PCI DSS as ID + title skeletons with customer-licensed text import; a common control set with crosswalk mappings |
| MCP server `grc` | Tools for agents: `grc.controls.search`, `grc.evidence.attach`, `grc.tests.record_result`, `grc.findings.create` (W2), `grc.risks.propose`, `grc.questionnaire.*`, `grc.mapping.suggest` |
| Agent templates (bundles) | Control tester, evidence collector, PBC responder, questionnaire answerer, vendor assessor, policy drafter, crosswalk mapper, regulatory watcher, risk analyst, remediation tracker, incident/breach coordinator, access-review coordinator, board reporter |
| Skills | SOC 2 report review, DPDP breach assessment, CSCRF ATR drafting, sampling methodology (CSCRF 100 %/25 % rule), risk scoring methods, OSCAL handling |
| Routines | CCM schedules per control test, regulatory feed polling, SLA nudges, campaign reminders, evidence freshness checks |
| UI | Web route group `/grc/*`: frameworks and controls, evidence, risks, vendors, findings, campaigns, auditor and vendor portals |
| Evals | Golden suites per agent template (crosswalk accuracy, questionnaire groundedness, SOC 2 exception extraction, Indian regulatory circular classification incl. Hindi) |

## 7. Plan changes (no change to M1)

M1 is unaffected. Its audit hash chain (M1-T05), permission catalogue and identity tables are reused as-is. Every core addition below is an additive migration in a later milestone.

### 7.1 Core tasks added to existing milestones (11)

| Task | Milestone | Title | Depends on |
|---|---|---|---|
| M3-T09 | M3 Agent builder | Content packs: bundle manifest with pack id/version, upgrade and uninstall semantics, signature verification | M3 bundle tasks |
| M5-T08 | M5 Policy & approvals | Reviews and sign-off on artifacts/records: statement + content-hash binding, multi-level chains, step-up, review queues and bulk review, re-sign on change | M5-T01..T07 |
| M5-T09 | M5 | Segregation-of-duties constraints for approvals and sign-offs (preparer ≠ reviewer ≠ approver, conflicting role pairs, agent-owner exclusion), simulated in policy simulation | M5-T08 |
| M7-T11 | M7 Knowledge | Strict grounding mode: claim-level citation enforcement; citations to tool results and evidence items; "why" panel data | M7-T07 |
| M13-T07 | M13 Observability & eval | Run records (record mode, sealed manifest, encrypted tool I/O, pinned model/params) and re-performance replay with divergence report; groundedness grader as a publish gate | M13-T04, M14-T08 for storage |
| M14-T08 | M14 Security & compliance | Evidence vault (`ar_domain.records`): immutable objects, sha256, WORM storage, optional RFC 3161 timestamps, service-key signatures, custody log, verification API | M14-T03 |
| M14-T09 | M14 | Legal hold and record-retention schedules across all record classes; disposition certificates | M14-T02, M14-T08 |
| M14-T10 | M14 | AI governance register: agent cards per published version, oversight metrics, AI incident log, AIMS evidence export | M13-T04 |
| M14-T11 | M14 | External guest principals (auditor/vendor): invitation, magic-link + TOTP or federated login, time-boxed scoped grants, download watermarking, full audit | M1 identity (additive), M14-T06 |
| M14-T12 | M14 | Report/binder export engine: record selection → PDF/XLSX/ZIP + hash manifest + offline verifier; review step for scheduled reports | M14-T08, M5-T08 |
| M14-T13 | M14 | Pack extension points: plugin router mount, pack Alembic environment helper, permission/audit-action registration, web nav slots, pack enable flags per tenant | M3-T09 |

Effect: 1.0 (M15-T07) gains these dependencies. Estimated +15–20 % on M5/M13/M14 effort; 1.0 remains generic.

### 7.2 GRC solution pack milestones after M15, or in parallel after M14 (23 tasks)

| Milestone | Goal | Tasks (indicative) |
|---|---|---|
| **M16 — GRC pack foundation** | Domain schema and catalogues usable by agents | T01 pack skeleton and `grc` schema/RLS; T02 frameworks/requirements/controls + OSCAL import/export; T03 common control set and crosswalk mappings with confirmation workflow; T04 evidence links to the core vault and freshness rules; T05 `grc` MCP server (read tools); T06 web: frameworks, controls, evidence |
| **M17 — Evidence connectors and CCM** | Continuous control monitoring end to end | T01 connector kit (read-only patterns, pagination, evidence capture helper); T02 AWS/Azure/GCP; T03 Okta/Entra/Google Workspace; T04 GitHub/GitLab + Jira/ServiceNow (findings sync); T05 control tests + CCM routines + results/findings; T06 eval suites for collectors and tests |
| **M18 — GRC agents, skills and workflows** | Templates for the high-value use cases | T01 questionnaire answerer + answer library + bulk review; T02 vendor risk (intake, assessments, SOC 2 review skill, tiering); T03 policy lifecycle + policy drafter + acknowledgement campaigns; T04 risk register + scoring + acceptance sign-off; T05 regulatory change watcher (RBI/SEBI/CERT-In/DPB feeds) + impact analysis; T06 incident/breach coordinator with regulatory clocks (CERT-In 6 h, DPDP/GDPR 72 h) |
| **M19 — Audit, access reviews and reporting** | Auditor-facing workflows | T01 PBC/request tracker + auditor portal (guest principals); T02 access-review campaigns + entitlement ingestion + SoD conflict rules; T03 attestation campaigns; T04 report templates (SoA, SOC 2 binder, CSCRF formats, DPDP breach report, board pack); T05 pack release, bundle signing, upgrade tests |

Suggested sequencing:
- Ship core 1.0 with §7.1 included.
- Start M16 once M14-T13 lands; it can run in parallel with M15.
- Timing: target M18-T06 (breach workflow) before 13 May 2027, when DPDP Rule 7 applies, and the CSCRF ATR/sampling features before the FY 2026-27 audit cycle (mid-2027).

### 7.3 Open questions to add (with recommended defaults)

| Proposed id | Question | Recommended default |
|---|---|---|
| OQ-21 | Trusted timestamping for evidence? | Optional RFC 3161 TSA URL per tenant; default off; sha256 + service signature + Object Lock always on |
| OQ-22 | Do guest principals reach agents? | No in 1.0: portals only; agent access for guests is a later, policy-gated feature |
| OQ-23 | Which framework texts ship? | Only freely licensed catalogues (NIST OSCAL, CSA CAIQ/CCM, Indian statutes/circulars); ISO/PCI/SOC 2 as ID skeletons plus customer import |
| OQ-24 | Pack schema migrations: separate Alembic environment or core linear history? | Separate environment and version table per pack; core keeps one linear history |
| OQ-25 | Run record storage cost | Record mode is opt-in per agent (default on for pack agent templates); encrypted tool I/O stored in the evidence vault with the record's retention class |

## 8. Uncertainties

- Regulatory dates come from official sources fetched today (MeitY DPDP Rules notification; EU AI Act Service Desk; SEBI/NSE/CDSL circulars). RBI 2026 directions were not reviewed in detail. Confirm sector specifics (RBI, IRDAI, SEBI category) with each buyer.
- Effort estimates are relative, not measured.
- Connector priorities assume Indian enterprise and BFSI buyers; validate with 3–5 design partners.
- "Reproducibility" must be positioned as recorded-and-re-performable, not deterministic regeneration: open-weight models served with temperature 0 and fixed seeds can still differ across hardware and batch sizes.
