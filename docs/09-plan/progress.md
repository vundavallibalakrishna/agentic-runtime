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
M2.5-T01b | done | 25593f8 | 2026-10-28 local verification passed: make check (460 Python, 85.21%), make test (478 Python, 85.77%), production build, 42 browser checks, six live SSO/widget checks, worker chat/ingestion/manual and scheduled routines; hosted CI pending; docs/testing/full-stack-review.md
M2.5-T01a | done | e73cd78 | 2026-10-27 workspace management/detail/state refinement implemented; web build/typecheck/lint/unit and light/dark mobile/desktop axe checks pass; make test passes (371 Python tests, 85.02%); the coverage and full Temporal/widget gaps are closed locally by M2.5-T01b; hosted CI remains outside verification; docs/testing/detail-flow-review.md

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

M21-T01 | done | 570ad4f | industry pack parked; removed in M30
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

M23-T01 | done | d517185 | durable connections, tools and model catalogue
M23-T02 | done | d517185 | read-only SQL tool
M23-T03 | done | d517185 | spreadsheets, charts, structured output
M23-T04 | done | d517185 | UI, Qwen proof, screenshots

M24-T01 | done | e2817ce | ingestion and durable extraction
M24-T02 | done | e2817ce | document tools with citations
M24-T03 | done | e2817ce | chunked retrieval for long files
M24-T04 | done | e2817ce | library screens, Qwen proof, screenshots

M25-T01 | done | 903e702 | knowledge bases, real embeddings, revision 0027
M25-T02 | done | 903e702 | memory visible across conversations
M25-T03 | done | 903e702 | portable skills loaded by description
M25-T04 | done | 903e702 | screens and Qwen3-32B proof

M26-T01 | done | fd5cc27 | durable installs, grants, oauth state, named secrets
M26-T02 | done | fd5cc27 | connector runtime and twelve definitions
M26-T03 | done | fd5cc27 | catalog screen
M26-T04 | done | fd5cc27 | proof and labels

M27-T01 | done | ddd29b9 | cloud signing, token cache, shared rate limit
M27-T02 | done | ddd29b9 | nine connector definitions
M27-T03 | done | ddd29b9 | catalog pages and guides
M27-T04 | done | ddd29b9 | proof and labels

M28-T01 | done | e74db42 | agent calls, parallel, handoff, budgets
M28-T02 | done | e74db42 | durable tool calls, approvals, policies, sandboxes, questions
M28-T03 | done | e74db42 | schedules, inbox, runs tree, editor selection

M29-T01 | done | e964d56 | agent API, hashed keys, idempotency, quota
M29-T02 | done | e964d56 | MCP server and approval-required writes
M29-T03 | done | e964d56 | A2A card, tasks, remote tool
M29-T04 | done | e964d56 | Expose tab

M30-T01 | done | 3bfd4b8 | retired pack removed; revision 0031 drops its schema

M31-T01 | done | 9aa4dd1 | final certification of the whole platform

M32-T01 | done | 0e34c9c | document analysis keeps evidence; paraphrased check |
M32-T00 | done | 938ab73 | review record, fresh-pass and GRC-flow evidence committed
M32-T02 | done | 574df81 | tenant-scoped settings reads; privacy.redactionSkipEntities
M32-T03 | done | 267de52 | requester-mode approvals accept another approver when SoD blocks the requester
M32-T04 | done | 267de52 | no fake echo outside dev/ci: run fails model_unavailable; gateway 502
M32-T05 | done | 43f9ab6 | scripted compose and keyword tool paths run only where fake models are allowed (dev/ci)
M32-T06 | done | 43f9ab6 | builder drafts with the reasoning model, repairs once from errors, scripted proposal last
M32-T07 | done | c775a9b | cost from model prices per call; usage events carry run/model ids, flush to usage_events and reload on bind; prices on the models API and screen
M32-T08 | done | 1c1e774 | models.request_options (revision 0032) replaces the Qwen3 name checks; API accepts requestOptions
M32-T10 | done | 1c1e774 | chart sets AR_APP_MODULE and AR_PORT per service and runs workers through their console scripts
M32-T09 | done | aab95f3 | features.assurance (default off) gates the assurance routes, permissions and nav; dev seed turns it on; neutral builder starter prompt; session reports tenant features and locale
M33a-T01 | done | 26f275a | seed users-mode W2 policy; fetch retry; search key path not_live without a key |
M33b-T01 | done | 2b6766c | OCR canary live on tesseract; image.ask live on Qwen2.5-VL, vision_unavailable on fake-llm |
M34a-T01 | done | 9c5080e | documents.create for DOCX, PDF and XLSX; fixture checklist |
M34b-T01 | done | f51262c | DuckDB sheet SQL, questionnaire write-back, chart themes and slide; fixture checklist |
M33c-T01 | done | e77c491 | tool-choice eval gym; dry-run scorecard 12/12; live Qwen behind AR_EVAL_GYM_LIVE |
M35-T01 | done | 2a6e30a | durability, Temporal dev-server schedule fire, cache eviction, A2A list and push, job progress |
M36-T01 | done | cb3f552 | connector live pack harness; dry CI; ledger promotes a recorded read |
M37-T01 | done | d4bdd66 | controlled browser on the M6 session; Chromium canary not_live when dump-dom does not finish |

M38-T00 | done | 7cc9a21 | tool review, M38 tasks, M39 to M42 outlines
M38-T01 | done | 8370ed6 | history, tool search and files read only the caller's rows
M38-T02 | done | 3fc0cfd | a handler failure is a tool error; a crashed turn ends the run
M38-T03 | done | 9cdd356 | demo fixtures seeded only in dev and ci, in every process; a stopgap that M38a-T07 deletes
M38-T03a | done | 94dea49 | browser tests retry twice in CI and report flaky tests

M38a-T00 | done | 213e943 | removal plan, review section D, the AGENTS.md rule, OQ-94
M38a-T01 | done | dbb5a3f | scripted model reached as an ordinary provider; ar_testing.stand_in
M38a-T02a | done | 28a33f0 | a provider or alias test reports a dead endpoint as failed
M38a-T02f | done | 4f572f4 | a tool-less agent's turn goes to the tenant's provider
M38a-T02b | done | dbf8826 | an eval case runs the agent; tool mocks in the pipeline; runs are queued and scored in the background
M38a-T03 | done | a7a85ee | the browser-test harness runs chat on the stand-in (reasoning alias) with a demo-chat script set covering each spec's answers and tool flows; a sandbox exec with an image output surfaces it inline (both loops), so the agent loop shows the chart it drew
M38a-T02c | done | eb30dfa | a delegated child runs the agent loop; the auto-retrieve knowledge answer is written by the tenant's model, not joined from snippets; the m7/m9 specs move onto the stand-in
M38a-T02d | done | bcae48f | the builder drafts with the tenant's model and returns the validation errors when a draft cannot be repaired; scripted_definition and the builder_scripts/builder_strict/builder_responder hooks leave the product
M38a-T02e | done | 6929a4b | the `slow` keyword and the `fake:`/bullet fallback leave `chat/service.py` `_tokens`; a tool-less turn with no connected model is an error; run completion callbacks fire on the agent-loop path too; the tests that read the in-process answer move to the stand-in
M38a-T04 | done | 4c237a8 | the keyword tool turn (`tools/chat_loop.py` `maybe_tools`, the `/tool` and `ask me` triggers) is deleted; only the approval pause stays; `generate` no longer runs it. `maybe_compose` and the m9 migration are T04a
M40-T06 | done | 47c5b2f | a tool's images (artifacts and the chart presentation) are shown to a vision-capable reasoning model as `image_url` parts, else the vision alias describes them; with no vision model the turn is unchanged; `tools/images.py` collects and builds the message, the agent loop injects it after each batch
M39-T01 | done | d37f45f | every core built-in tool parameter has a description, an enum where closed and an item schema for arrays; `scripts/check_tool_descriptions.py` fails the docs job on a gap (connectors deferred to T01a); `prompts/text/tool_use.md` tells the model to choose and fill a tool from its description
M39-T02 | done | 7ed5844 | the sandbox (Computer) file and command tools are retired from the model's view and a stored `sandbox` binding resolves to the general equivalents (`pipeline._bound`/`_entitled`); the analyst and showcase writer bind `general`; image files render inline on any tool card, not only a chart; execution reroute to the container is M40-T01
M39-T03 | done | 87f4485 | general gains `edit_file`/`grep`/`glob`/`move`/`delete` and `read_file` by line range; write primitives are W1; `snapshot_workspace` prunes the saved row of a file removed from disk so a move or delete sticks across a turn's later calls; `files.read` offsets documented as bytes
M39-T04 | done | 652a99a | above the tool threshold the loop sends only the core tools and the search tool; a searched tool's schema joins the next model call; `control.search` ranks only the agent's granted tools (F45); the durable per-tenant-and-model vector table is T04a
M39-T05 | done | 7776f11 | the pre-turn skill match only hints (names the skill, no body); `skills.load` joins `_IMPLICIT` and is offered whenever the agent has a skill; the model loads the body itself; the skill list is already in the prompt
M39-T06 | done | d0a7771 | the MCP client keeps every content block of a result (all text joined, image and resource named, full result in structured) and follows `tools/list` pages in one streamable session; reusing a session across a run's calls is T06a
M39-T01a | done | d2a55f8 | every connector tool parameter has a description (a shared map in `connectors/catalog.py` `tool_records`, since the 92 tools share 72 common param names); `connectors` leaves the lint's `DEFERRED_SERVERS`, so the lint now covers all 163 built-in tools
M39-T06a | done | 2b199af | within a run, calls to one MCP server reuse a single session (`call_remote` takes the run id, caches a `(server, run)` session on the store, initialises once, re-initialises once on a dropped session); the pipeline passes the run id
M39-T04a | done | c5891e9 | revision 0035 adds `tool_search_vectors` (tenant_id + RLS + grants, vector as jsonb, ORM model in `durability/tables.py`); `tools/search.py` writes computed vectors to the durable book and loads them on `_kept`, flushed/hydrated like the M35 books, so the first search after a restart ranks by meaning (OQ-106)
M40-T01 | done | f4208e3 | `sandbox-agent` runs `sandbox.exec` and file operations inside its workspace: a command with a confined cwd, a timeout that kills the group (124), new-file tracking, byte-range and base64 reads/writes, recursive list, and the cumulative cpu usage; the `ar-sandbox` image, the manager's aiodocker driver and the runtime wiring are T01b/T01c/T01d
M40-T01b | done | a5eee3c | `images/sandbox/Dockerfile` bakes the sandbox-agent (uv sync --package ar-sandbox-agent) with git/curl/jq/ripgrep as uid 10001; the placeholder health server is gone; CI's images job builds it; verified by running the container and executing a command that wrote a file (the scientific-Python set and LibreOffice are T02)
M40-T01c | done | 0a358a3 | the manager's docker driver (`drivers/docker.py` `start_sandbox`/`stop_sandbox`, aiodocker) starts an `ar-sandbox` container, waits for the agent's `/healthz`, returns its endpoint and token, and removes it on stop; a canary integration test starts a real container, runs a command through the agent's `/mcp`, and checks the token is enforced
M40-T01d | done | 6fade67 | when a sandbox carries an `endpoint_url`, `sandboxes/runtime.py` proxies `exec`/`read_file`/`write_file`/`list_files` to the agent inside the container (httpx) and exports the files a command wrote as artifacts (read back over the proxy), with a chart presentation for images; the host subprocess stays the default; a canary integration test runs the tools in a real container. Starting the container and stamping the endpoint is M40-T01e
M40-T01e | done | 5c29768 | the in-process path starts a container. `ensure_scope` calls an injected `store.sandbox_launcher` when the row's driver is `docker`, stamping `endpoint_url`/`container_id`/`agent_token` (and `_terminate` stops it); the aiodocker primitive moves to `ar_common.sandbox_docker` (with a sync, loop-safe `DockerSandboxLauncher`) so the api/runtime register it without importing the manager (the manager's docker driver re-exports it). The api registers the launcher when `AR_SANDBOX_IMAGE` is set and the install allows an unisolated sandbox; with no launcher the tools run on the host, as before. A start failure fails the sandbox cleanly (`SandboxStartError`) rather than falling back. A docker-gated integration test drives the whole wired path: `ensure_scope` starts a real container and `run_tool exec` runs inside it
M40-T02 | done | f765b20 | the full computer image. `images/sandbox/Dockerfile` adds the document/OCR/media stack on top of the agent: the pinned Python toolbox `images/sandbox/sandbox-tools.txt` (pandas, numpy, polars, scipy, matplotlib, seaborn, openpyxl, python-docx, python-pptx, reportlab, pypdf, pdfplumber, duckdb, pillow, pytesseract — compiled with `uv pip compile --universal` for 3.14 and installed into the agent venv so `python3` finds them), LibreOffice headless, poppler-utils, tesseract (`SANDBOX_TESSERACT_LANGS`, default `eng`), ffmpeg, and Noto fonts incl. CJK. CI's `images` job builds it; the toolbox resolves and installs on 3.14 (verified locally). Node/Chromium/Playwright stay for M40-T04
M40-T04a | done | c50d5c3 | the browser image. `images/sandbox/Dockerfile` gains `ARG WITH_BROWSER=0`: when `1` it installs Node 24 (`NODE_VERSION`, official tarball) with pnpm (corepack), and Playwright (`images/sandbox/browser-tools.txt`, playwright 1.64.1 pinned for 3.14) with its Chromium (`playwright install --with-deps chromium` into `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, owned by the sandbox user). CI's default build leaves it out so the image stays small (OQ-37/OQ-87); the browser image is built with `--build-arg WITH_BROWSER=1` and verified locally (Playwright drives a real page inside the container). The agent browser tools (T04b) and the runtime routing that retires M37's in-process parser (T04c) follow
M40-T04b | done | 16aebb9 | the agent's Playwright browser tools. New `services/sandbox_agent/.../browser.py` drives real Chromium with the async Playwright API (the agent's `/mcp` route is async; sync Playwright can't run in the loop): `navigate`, `snapshot` (tags every visible interactive element with a `data-ar-ref` and returns an outline of refs + page text), `click`, `type`, `press`, `select`, `hover`, `scroll`, `wait_for`, and a real `screenshot` (PNG base64) — keeping M37's tool names/shapes. One Playwright context per container = inherent cookie isolation. Playwright is a locked optional dep (`ar-sandbox-agent[browser]`, installed by the image via `uv sync --extra browser`); imported lazily so the default image and unit job do without it (returns `browser_unavailable`). `browser-tools.txt` removed. Verified: unit tests (helpers + not-installed path) and a docker-gated integration test where the agent navigates, snapshots, clicks (page text changes) and screenshots a real page in the container. Runtime routing + retiring M37 is T04c
M40-T04c | done | 2a910d3 | the runtime routes the browser tools to the container. `sandboxes/runtime.py` `_browser`: when the sandbox has an `endpoint_url`, `_browser_remote` proxies the browser tools to the agent's real Chromium (`_proxy`/`_agent_post`), applying the **same** egress gate before a navigation — M37's gate is extracted to `browser.navigate_decision` and shared by both paths; a denied/approval-pending host returns `egress_denied` and never reaches the container. A real `screenshot` is decoded and stored as a `browser.png` artifact with an inline chart presentation (`engine: chromium`), replacing M37's fixed fixture image. `submit_form` added to the agent. **M37's in-process browser is KEPT as the no-container fallback** (host-path parity), not retired — full retirement + real egress isolation is T03/Squid (OQ-119). Verified: unit tests (gate blocks a denied host, reads proxy through, real screenshot → artifact) and a docker-gated integration test driving snapshot/navigate-denied/screenshot through `run_tool` against a real browser container
M40-T05a | done | 6c4e46d | browser file flows. Agent `browser.py` gains `save_pdf` (Chromium `page.pdf`), `download` (Playwright `expect_download`, capped 25 MiB, base64) and `upload` (`set_input_files` from a confined workspace path); the runtime generalises the screenshot artifact path into `_remote_capture` (decodes the base64 field, stores a `browser.png`/`page.pdf`/download artifact, inline chart only for images) and routes the three; the model surface adds them (browser server 8→11 tools, descriptions covered by the lint). Routing is unit-proven (`test_m40_browser_routing.py`: save_pdf→PDF artifact, upload→proxy); the docker-gated integration test adds a save_pdf step but was not re-run locally this session (a system memory reap stopped the browser-image rebuild), so the file flows' container run is pending — the browser pipeline itself is proven by M40-T04c. Tabs are T05b, stored sign-in T05c
M40-T05b | done | ab07e0f | browser tabs. Agent `_Session` now tracks its context's pages with an active tab; new tools `tabs` (list index/title/url/active), `new_tab` (open blank + activate), `switch_tab`/`close_tab` (by index). They return a snapshot or the tab list, so the runtime routes them through `_browser_remote`'s existing `_proxy` (no new routing). Model surface +4 (browser server 11→15; lint 170). Tests: routing unit (`tabs`→proxy) + agent membership; the docker-gated canary opens/lists/switches/closes a tab against a real container (batched with the T05a save_pdf check in one image build). Stored sign-in is T05c
M40-T05c | done | ace5853 | stored, per-connection browser sign-in (increment 1: trusted claim-time restoration). New `sandboxes/browser_auth.py`: a `BrowserConnectionBook` seals a site's storage state (cookies/storage) with `connection_key()`, scoped to tenant+owner (reusing the service-connection crypto); `restore_into_context` unseals it in the TRUSTED runtime at claim time, checks tenant ownership + status (revoked/active), and injects the state into a FRESH isolated container context over the agent's new trusted `/admin/session` endpoint (not `/mcp`). The model calls `use_connection(connection)` with only the connection name and gets back an opaque handle + status — the state never enters model context, a tool arg, a snapshot, a log or an error. Audit actions `browser_connection.created/restored/revoked/denied` (catalogue + enum). Mandatory security tests (`test_m40_browser_auth.py`, 7): cross-tenant isolation, spoofing, revocation, no-container, secret non-disclosure (state reaches the trusted channel but never the model result/view/audit), audit-without-state. Batched docker canary restores a connection through `run_tool` against a real container. **DEFERRED to follow-ups:** OAuth connections (T05d), trusted scripted-login Auth Worker + MFA/CAPTCHA human-in-loop (T05e), full lifecycle — expiration/refresh/concurrency controls — and a durable `browser_connections` table with RLS (OQ). No agent access to cookies/localStorage/CDP/arbitrary JS (the fixed tool set already enforces this)
M40-T05d | in_progress | - | browser sign-in session lifecycle. Connections carry a `version` and an optional `expires_at`; `restore_into_context` refuses an expired connection (status→expired, audited) and stamps the connection id+version onto the sandbox. New trusted agent endpoint `/admin/session/export` returns the context's current `storage_state`; `save_session` (model tool, no args) captures it through that trusted channel, re-seals it to the connection THIS sandbox restored (never an arbitrary one), bumps the version, and audits `browser_connection.updated` — the captured state never reaches the model result or the audit. A stale save (another run advanced the version) is refused with `conflict` (optimistic concurrency). Tests `test_m40_browser_auth.py` +4 (expiration, capture+reseal+version, stale-conflict, save-without-signin) + the batched container canary saves a session. 172 tools. Remaining T05: scripted-login worker + MFA (T05e)
M38b-T00 | done | b367b5b | fresh tenant run on an empty database, the strict rules in AGENTS.md, the M38b plan, OQ-96 to OQ-98
M38b-T01 | done | 645a631 | every process registers the whole schema; a retry saves a finished turn
M38b-T02 | done | 928a4c7 | bootstrap creates only a tenant and its admin; scripts/seed_tenant.py also creates the sign-in account
M38b-T03 | done | b4f06c4 | a process reads its tenant and people from the database and holds no demo tenant; sign-in and the session use the tenant's rows
M38b-T03a | done | 8e62d47 | the workers follow the API's loopback rule
M38b-T04a | done | 767debf | the seed writes the assistant and the builder, owned by the admin; no request creates an agent; no Helpdesk for a real tenant
M38b-T04b | done | a110ea4 | no process falls back to a demo tenant; the browser tests start the API through a harness that owns it
M38b-T04c | done | 0a82979 | a product store starts with no tenant; tests build the demo tenant with ar_testing.demo; a test guards against product code building it
M38b-T05a | done | 64cea82 | the browser tests sign in through a path that exists only in their harness
M38b-T05b | done | 9a9498f | one sign-in: dev-login, the fixed users and the memory identity are out of the product; scripts sign in through Keycloak
M38b-T05c | done | 395d9f6 | a failed session check replaces the page with an error and a retry; the server-side gate is M38b-T05d, after M38-T09
M38b-T04e | done | 38b404c | a product store starts with no model provider, model or alias; fake-llm is part of the demo tenant
M38b-T07a | done | 85a2966 | provider, model and alias changes are saved and reach every process; one tenant-scoped loader; a key can be replaced; loopback is refused by default
M38b-T07b | done | 83fb55d | knowledge and memory embed with the model the embed alias names and refuse without one; no built-in model, provider guess or in-process vector; unscored search without a rerank model
M38b-T07c | done | d0bbcd1 | the Models screen adds, edits, tests and removes providers, models and aliases with nothing filled in; the aliases the product calls are listed with whether each is set; reading images is a model setting
M38b-T12 | done | 5aaed62 | what a turn remembers is decided by the tenant's model after the answer; no keyword patterns; a worker's memory is saved and reaches every process; a deleted memory is forgotten everywhere
M38a-T06 | done | ee8ef30 | tools are ranked by the tenant's embedding model and by shared words, never by a hash vector; a search never waits for the catalogue to be embedded; revision 0034 empties the stored vectors
M38b-T08 | done | 514cd48 | the prompt names each attached file with its id and path; a worker loads the conversation's files before a turn; one working folder and one way to name a file across file tools and code; the folder carries to the next turn; both live chats answer from the files since T09 and M38-T09
M38b-T09 | done | c2ecec7 | a kind of personal data is masked only when the tenant lists it and the match is sure enough; names, places and dates are off by default; the engine and its language model ship with every install; the kinds and the bar are on the Policies screen
M38-T09 | done | 0f13d68 | a tool handler stays on the loop thread and only its waiting moves to a worker thread; a long tool call no longer stops the process or cancels the turn; a call may use the time the run has left
M38-T05 | done | 61e833d | the tool guidance and the output schema are part of the system prompt on every path; the guidance says to compute with a tool and to state only what a tool returned
M38b-T10a | done | b31faa7 | the organisation's list of hosts is the ceiling and an agent only narrows it; a refusal comes before any network call and says where to change the list; loopback is an install setting; a settings change is audited with what changed
M38b-T10 | done | 23985e4 | every failure ends a run one way, the reply is marked failed with the reason, and the chat draws it as a failure with a retry
M38b-T08a | done | adeba98 | a sent message shows its files; several files per message; the composer offers the types the tenant allows; the upload rules are the tenant's settings
M38b-T14 | done | 816d46b | no form starts with a value the person did not type; save buttons wait for what they need
M38b-T09a | done | c7ecc89 | a masking token is drawn as inline code, so a line that starts with one is shown
M38b-T07d | done | 339ef7a | memory embeds its facts again by itself after the `embed` alias moves; an unscored knowledge search shows how close each passage is; the rerank route and bar are settings of the model
M38b-T13 | done | 7fb121e | every accepted upload is kept: bytes in the object store under the row's key, the row in `files`, fetched by whichever process needs them; `file_blobs` migrated at hydrate; upload body limits raised (F67)
M38b-T15 | done | b26bf0d | a conversation with no computer answers `{sandbox: null}` with 200, not a 404 the browser logs on every chat (F63)
M38b-T16 | done | 7e2d797 | no region or industry in a default: tenant/user timezone UTC and locale en, usage and quota fallbacks UTC, the schedule label reads the offset, the policy time helper offers UTC and the tenant's own zone, the `/grc` stub is removed (F55)
M38b-T17 | done | 11ed0c6 | a failed Knowledge or Memory screen shows a finished `ErrorState` card with a working Try again, not plain text with a bare link (F30)
M38b-T18 | done | d7901fe | no behaviour follows `AR_ENV`'s name: wildcard egress, unisolated sandboxes and the upload scanner are each a setting with a safe default (F60)
M38b-T19 | done | 5d0d1ca | a tool failure the answer already explains gets no extra "not recovered" notice; the acknowledgement words are broadened (F59)
M38b-T20 | done | e7a1086 | a recalled memory is framed as known about the person, so the model uses it instead of disclaiming access (F34)
M38b-T11 | done | fdd77ef | the fresh-tenant run is a repeatable pre-release gate (`scripts/fresh_run/`): a seeded tenant through sign-in, model setup, chat, knowledge search and memory recall, pass/fail and a screenshot per step; proved on the live acme tenant
M38b-T06 | done | 991031e | `python -m ar_domain.migrations.run` only migrates; the dev seed it ran after migrating is gone (F7 remnant); Helm and make already seed separately
M38b-T04d | done | ca79384 | the eval gym stops building the demo tenant in the product package: `build_world`/`run_suite`/`cli.main` take a seeded store, built by `scripts/m33c_eval_gym.py` via `ar_testing`
M38b-T04d | done | 6bd71fb | the eval suite command stops building the demo tenant too: `ar_system.evals.cli.main` takes a seeded store, built by `scripts/run_suites.py` via `ar_testing` (`make eval`); the guard now finds no demo-tenant building in any product package
M38b-T04f | done | 606bbea | the showcase half moved to ar_testing (`showcase_build`, `showcase.*`)
M38b-T04f | done | 8dd7bfc | `seed_demo_tenant`/`seed_demo`/`_seed_scripted_provider` move to `ar_testing.demo_tenant`; no demo-tenant building remains in any product package
M38b-T05d | done | - | the web middleware gates every workspace page server-side: no `ar_session` cookie redirects to sign-in, a present one is validated against the API; nothing of the workspace reaches a browser that is not signed in; sha recorded with the next task
