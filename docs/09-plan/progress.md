# Progress

One line per task: `id | status | commit | notes`.

M0-T01 | done | 820e3dd | monorepo skeleton
M0-T02 | done | 820e3dd | pins re-verified 2026-10-20
M0-T03 | done | 820e3dd | ar_common core
M0-T04 | done | 820e3dd | clients, telemetry, internal JWT
M0-T05 | done | 820e3dd | HTTP template and service mains
M0-T06 | done | 820e3dd | compose stack
M0-T07 | done | 820e3dd | fake-llm
M0-T08 | done | 820e3dd | web skeleton
M0-T09 | done | 820e3dd | codegen, including Zod from Pydantic and CLAUDE.md from AGENTS.md
M0-T10 | done | 820e3dd | CI
M0-T11 | done | 820e3dd | images
M0-T12 | done | 820e3dd | ar_testing fixtures

M1-T01 | done | 6a865cb | database core, tenant session, repository
M1-T02 | done | 6a865cb | Alembic revisions 0001-0005; CI migrations job
M1-T03 | done | 6a865cb | identity schema, permissions, idempotent seed
M1-T04 | done | 6a865cb | RLS and cross-tenant integration tests
M1-T05 | done | 6a865cb | append-only audit hash chain
M1-T06 | done | 6a865cb | outbox, relay decisions, idempotency middleware
M1-T07 | done | 6a865cb | secret metadata API and encrypted/vault stores
M1-T08 | done | 6a865cb | OIDC BFF login, session, CSRF, step-up
M1-T09 | done | 6a865cb | request pipeline, permissions, rate limits
M1-T10 | done | 6a865cb | tenant, users, invitations, groups, teams, me
M1-T11 | done | 6a865cb | roles, service accounts, API keys, audit read
M1-T12 | done | 6a865cb | domains, identity providers, SCIM
M1-T13 | done | 6a865cb | tenant provisioning plan, platform admin, signup
M1-T14 | done | 6a865cb | notifications, webhooks, signed camelCase bodies
M1-T15 | done | f60357c | sign-in page and admin users shell
M1-T16 | done | adf0e2d | public JSON via ApiModel; requestId; GET /me displayName and createdAt

M2-T01 | done | 1460d56 | model registry, migration 0006, SSRF allow-list
M2-T02 | done | 1460d56 | usage events, daily rollup, migration 0007
M2-T03 | done | 1460d56 | model-gateway breaker and parameter merge
M2-T04 | done | 1460d56 | definitions and stream contracts already in ar_contracts
M2-T05 | done | 1460d56 | agents registry, migration 0008, published assistant
M2-T06 | done | 1460d56 | conversations and runs, migration 0009
M2-T07 | done | 1460d56 | files API, scan decisions, migration 0010
M2-T08 | done | 1460d56 | in-process SSE with per-user cap
M2-T09 | done | 1460d56 | agent run advance for model steps only
M2-T10 | done | 1460d56 | runs API and signed callback helper
M2-T11 | done | 1460d56 | web chat with streaming, empty and error states
M2-T12 | done | 1460d56 | regenerate, edit, branches, feedback, share, export
M2-T13 | done | 1460d56 | models admin and dev login without an external key

M2.5-T01 | done | e29016a | design system, shell, sign-in, chat, restyled pages
M2.5-T02 | done | e29016a | Keycloak callback and local-run bugs
M2.5-T03 | done | e29016a | fresh-clone CI job
M2.5-T04 | done | e29016a | checklist, screenshots, walkthrough
M2.5-T01b | in_progress | 25593f8 | 2026-10-28 local verification passed: make check (460 Python, 85.21%), make test (478 Python, 85.77%), production build, 42 browser checks, six live SSO/widget checks, worker chat/ingestion/manual and scheduled routines; hosted CI pending; docs/testing/full-stack-review.md
M2.5-T01a | in_progress | e73cd78 | 2026-10-27 workspace management/detail/state refinement implemented; web build/typecheck/lint/unit and light/dark mobile/desktop axe checks pass; make test passes (371 Python tests, 85.02%); the coverage and full Temporal/widget gaps are closed locally by M2.5-T01b; hosted CI remains outside verification; docs/testing/detail-flow-review.md

M3-T01 | done | 8d6d5b0 | lifecycle API, access rules, audit and domain events
M3-T02 | done | 8d6d5b0 | schema then reference validation, definition hash
M3-T03 | done | 8d6d5b0 | prompt assembly, budget, wrapping, prompt hash
M3-T04 | done | 8d6d5b0 | preview conversations for draft versions
M3-T05 | done | 8d6d5b0 | bundle export and dry-run import
M3-T06 | done | 8d6d5b0 | draft-from-description with one repair
M3-T07 | done | 8d6d5b0 | builder UI, form and YAML, Playwright and axe
M3-T08 | done | 8d6d5b0 | catalogue, search, filters, favourites, chat
M3-T09 | done | 8d6d5b0 | content packs, signatures, migration 0020
M3-T10 | done | 8d6d5b0 | builder agent, sessions, apply creates a draft

M4-T01 | done | 6f82810 | tool tables, registry API, seeded built-ins
M4-T02 | done | 6f82810 | credential providers, connections, encrypted token cache
M4-T03 | done | 6f82810 | mcp-gateway pipeline
M4-T04 | done | 6f82810 | runtime tool turn
M4-T05 | done | 6f82810 | built-in files, web, plan, tool search
M4-T06 | done | 6f82810 | mcp-openapi
M4-T07 | done | 6f82810 | mcp-sql and data connections
M4-T08 | done | 6f82810 | connector SDK and ticketing example
M4-T09 | done | 6f82810 | test console, call log, drift
M4-T10 | done | 6f82810 | tools UI and visual test

M5-T01 | done | 99000ef | policy tables, service, bundle, API
M5-T02 | done | 99000ef | Rego package and Python fallback
M5-T03 | done | 99000ef | gateway policy and approval integration
M5-T04 | done | 99000ef | approvals API and standing approvals
M5-T05 | done | 99000ef | runtime approval and user-input waits
M5-T06 | done | 99000ef | policy simulation and embedded tests
M5-T07 | done | 99000ef | web approvals, policies, chat card
M5-T08 | done | 99000ef | reviews and sign-off
M5-T09 | done | 99000ef | segregation of duties

M6-T01 | done | c587f91 | sandbox templates and revision 0013
M6-T02 | done | c587f91 | sandbox agent and image
M6-T03 | done | c587f91 | sandbox-manager and local driver
M6-T04 | done | c587f91 | pod spec, network policy, warm pool
M6-T05 | done | c587f91 | egress allowlist and Squid helper; proxy stays up under make up --wait
M6-T06 | done | c587f91 | gateway routing and reaper
M6-T07 | done | c587f91 | browser tools
M6-T08 | done | c587f91 | file previews and download headers
M6-T09 | done | c587f91 | artifacts, computer panel, Computers page

M7-T01 | done | 791133d | revision 0014 and collections/sources/documents API
M7-T02 | done | 791133d | RetrievalStore, pgvector, conformance, retrieval
M7-T03 | done | 791133d | ingest pipeline and activities
M7-T04 | done | 791133d | source sync, web and S3 connectors
M7-T05 | done | 791133d | SharePoint, Confluence, Google Drive, ACL sync
M7-T06 | done | 791133d | reindex, delete, source operations
M7-T07 | done | 791133d | citations in the runtime
M7-T08 | done | 791133d | knowledge pages and citation UI
M7-T09 | done | 791133d | Qdrant adapter and conformance-qdrant
M7-T10 | done | 791133d | migrate-store CLI and pgvector/qdrant parity copy
M7-T11 | done | 791133d | strict grounding mode

M8-T01 | done | a70a7bd | revision 0015 and memory API
M8-T02 | done | a70a7bd | memory tools and recall
M8-T03 | done | a70a7bd | extraction workflow
M8-T04 | done | a70a7bd | compaction
M8-T05 | done | a70a7bd | memory settings, review queue, chat indicator

M9-T01 | done | 544422f | subagent delegation, child runs, children API
M9-T02 | done | 544422f | revision 0016 and skills API
M9-T03 | done | 544422f | skills.load, sandbox assets, loaded skills
M9-T04 | done | 544422f | skills editor, trace graph, visual test

M10-T00 | done | e5e55c3 | durable process-store cutover
M10-T01 | done | 29540c8 | routines schema and API
M10-T02 | done | 29540c8 | routine run workflow
M10-T03 | done | 29540c8 | webhooks, polls, channel events
M10-T04 | done | 29540c8 | delivery tools
M10-T05 | done | 29540c8 | routines web UI

M11-T01 | done | bba37e5 | revision 0018, integration API, durable channel posts (OQ-41)
M11-T02 | done | bba37e5 | inbound routing, threads, internal channel endpoints
M11-T03 | done | bba37e5 | Slack events, commands, interactions, mrkdwn
M11-T04 | done | bba37e5 | Teams activities, Bot Framework JWT, Adaptive Cards
M11-T05 | done | bba37e5 | email accept, SPF check, SMTP reply (OQ-42 in-process mailbox)
M11-T06 | done | bba37e5 | OpenAI chat facade and widget session
M11-T07 | done | bba37e5 | notification fan-out to channel DMs, email fallback
M11-T08 | done | bba37e5 | admin channels page and profile linking

M12-T01 | done | c259bc9 | quotas API, counters, enforcement hooks
M12-T02 | done | c259bc9 | plan limit check on every creation path
M12-T03 | done | c259bc9 | usage summary, CSV, me and platform reports
M12-T04 | done | c259bc9 | usage and quotas screens, my usage, quota chat state

M13-T01 | done | aca3c20 | telemetry, dashboards, alerts, no-content spans
M13-T02 | done | aca3c20 | overview, platform health, trace links
M13-T03 | done | aca3c20 | revision 0019 and eval catalogue API
M13-T04 | done | aca3c20 | eval workflow, graders, publish gate, platform suites
M13-T05 | done | aca3c20 | run inspector, evals UI, platform health
M13-T06 | done | aca3c20 | feedback digest and alias-change re-runs
M13-T07 | done | d3097a8 | run records, replay, groundedness gate after the evidence vault

M14-T01 | done | d3097a8 | guardrails, injection classifier, Indian PII recognisers
M14-T02 | done | d3097a8 | retention sweep, erasure, data export
M14-T03 | done | d3097a8 | audit export, SIEM fan-out, chain verification
M14-T04 | done | d3097a8 | security headers, SSRF guard, upload limits
M14-T05 | done | d3097a8 | signing-key envelope, supply-chain job already in CI
M14-T06 | done | d3097a8 | metadata support grant cannot read content
M14-T07 | done | d3097a8 | verification log; no accepted risks
M14-T08 | done | d3097a8 | evidence vault, records tools, revision 0023
M14-T09 | done | d3097a8 | legal hold, retention schedules, disposition certificates
M14-T10 | done | d3097a8 | AI register cards, incidents, oversight, export
M14-T11 | done | d3097a8 | guest principals, magic link, TOTP, watermark
M14-T12 | done | d3097a8 | binder ZIP and stdlib verifier
M14-T13 | done | d3097a8 | pack extension hooks, import-linter contract

M15-T01 | done | f8c1311 | umbrella chart, presets, schema, kubeconform
M15-T02 | done | f8c1311 | bundled or external stateful dependencies; Qdrant off by default
M15-T03 | done | f8c1311 | backup CronJobs and fixture restore drill; live PITR is OQ-48
M15-T04 | done | f8c1311 | Locust scenarios and in-process probe; 24h soak is OQ-48
M15-T05 | done | f8c1311 | rolling update, migrate hook, worker build ids, SSE resume
M15-T06 | done | f8c1311 | air-gap image list, mirror script, lockdown overlay
M15-T07 | done | f8c1311 | changelog, release workflow dry-run; live Slack/Teams/IdP are OQ-48

M16-T01 | done | cb85ca9 | schema grc, RLS, manifest; core does not import the pack
M16-T02 | done | cb85ca9 | OSCAL catalogues, skeletons, licensed-text import
M16-T03 | done | cb85ca9 | common controls and two-person crosswalk confirm
M16-T04 | done | cb85ca9 | evidence links, freshness, cross-tenant 404
M16-T05 | done | cb85ca9 | grc read tools; disabled tenant is tool_server_unavailable
M16-T06 | done | cb85ca9 | /grc frameworks, controls and evidence screens
M16-T07 | done | cb85ca9 | entity tree and posture in pack revision 0001

M17-T01 | done | 6636c87 | connector kit, page cap, backoff, stable request hash
M17-T02 | done | 6636c87 | AWS, Azure and GCP read collectors and evidence capture
M17-T03 | done | 6636c87 | Okta, Entra and Google Workspace collectors
M17-T04 | done | 6636c87 | GitHub, GitLab, Jira and ServiceNow; W2 writes store external_ref
M17-T05 | done | 6636c87 | control tests, findings, grc-ccm, close guard; HTTP stays on the process store (OQ-50)
M17-T06 | done | 6636c87 | collector and control-test evals; a missing evidence hash fails the gate

M18-T01 | done | 0186422 | answer library, grounded drafts, export guard, bulk review
M18-T02 | done | 0186422 | vendors, SOC 2 skill, guest portal vendor
M18-T03 | done | 0186422 | policy publish waits for sign-off; acknowledgement campaign
M18-T04 | done | 0186422 | risk score history; acceptance audit after sign-off
M18-T05 | done | 0186422 | feeds, robots and SSRF, Hindi circular, cscrf-sampling
M18-T06 | done | 0186422 | breach clocks and filing after sign-off; no silent hold
M18-T07 | done | 0186422 | waiver control required; expiry sweep ignored by tests
M18-T08 | done | 0186422 | ethics cases hidden without grc.ethics:manage; HTTP on the process store (OQ-51)

M19-T01 | done | 15da601 | PBC tracker, XLSX import, auditor guest grant and watermarked response
M19-T02 | done | 15da601 | entitlement ingest and business SoD flags; core sod_constraints unchanged
M19-T03 | done | 15da601 | campaign start, close and statement-hash sign-off; reminder routine
M19-T04 | done | 15da601 | five report templates through the core binder; board pack waits for sign-off
M19-T05 | done | 15da601 | signed 1.1.0 upgrade keeps a control; pack revision 0002; core head unchanged
M19-T06 | done | 15da601 | inspection room; guest grant is that binder only
M19-T07 | done | 15da601 | DSAR erasure skips a hold; consent requires evidence
M19-T08 | done | 15da601 | resilience fail needs evidence; model assets do not write agent cards

M20-T01 | done | 0cb867c | registered provider routing
M20-T02 | done | 0cb867c | operator model screen
M20-T03 | done | 0cb867c | full-stack certification run
M20-T04 | done | 0cb867c | report, checklist and walkthrough

M21-T01 | done | 570ad4f | GRC pack parked behind AR_GRC_PACK_ENABLED, default off
M21-T02 | done | 570ad4f | chat home, agent and model pickers, tool progress
M21-T03 | done | 570ad4f | plan, act, check, retry; assistant max_tool_calls 8
M21-T04 | done | 570ad4f | agent form, editor limits, model connection, real Qwen proof

M21b-T01 | done | 709dde5 | per-run sandbox and workspace files
M21b-T02 | done | 709dde5 | fetch, search provider, HTTP with approval
M21b-T03 | done | 709dde5 | builder toggles, tool cards, Qwen proof

M22-T01 | done | f4ba7d1 | named encrypted connections
M22-T02 | done | f4ba7d1 | MCP client, approval and untrusted results
M22-T03 | done | f4ba7d1 | OpenAPI import and described tools
M22-T04 | done | f4ba7d1 | registry, builder, Qwen proof
