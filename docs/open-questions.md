# Open questions

The single place for undecided points. Every question has a **recommended default that implementers apply now**; changing a default later is a product decision recorded here (status `decided` with date). Task text that disagrees with a spec is also recorded here ([plan README](09-plan/README.md#task-format)).

| ID | Question | Recommended default (apply now) | Affects | Status |
|---|---|---|---|---|
| OQ-01 | Do we need a message broker (Kafka or similar) for events? | **No** in v1: transactional outbox + Valkey streams + Temporal cover all flows ([domain-events](05-contracts/domain-events.md)). Revisit if outbound event volume exceeds 5,000/s sustained or external consumers need replay beyond webhooks. | spec 20, scope | open |
| OQ-02 | Should the widget support anonymous (not signed-in) visitors? | **No**: every widget session maps to an existing active user via a host-signed JWT ([spec 16 §7](03-specs/16-channels.md#7-web-widget-feature-widget)). Public chatbots are a non-goal. | spec 16, scope | open |
| OQ-03 | Provide a web search tool? | **No** in v1 (no third-party search APIs; air-gapped installs). `web.fetch` and the browser reach only allowlisted hosts. A tenant can register an internal search service as an MCP tool. | spec 08 §9, deployment-modes §4 | open |
| OQ-04 | Multi-currency / cross-currency billing? | **No conversion**: each tenant has one `billing_currency`; platform models priced in `AR_BILLING_CURRENCY` (default `INR`); usage reports are in micro-units; no invoicing engine. | spec 17 §2 | open |
| OQ-05 | Upload files natively to Teams? | **Links**: Teams replies link to the web app (native upload needs a per-user consent flow). Slack uploads artifacts natively. | spec 16 §4 | open |
| OQ-06 | What do W2/W3 tool calls do before policies and approvals exist (M4 → M5)? | **Denied** with `error.code=policy_denied` and message "approvals are not enabled yet" by the interim `PolicyDecider`; replaced in M5-T03. Never shipped to customers (M5 precedes 1.0). | M04, M05 | decided (2026-10-20) |
| OQ-07 | When to partition large tables? | **Unpartitioned** in v1; convert `messages`, `run_events`, `usage_events`, `audit_events` to monthly range partitions when a table exceeds ~200 M rows or autovacuum cannot keep up (procedure [rb-12](07-ops/runbooks.md#rb-12-partition-a-large-table), [migrations §4](04-data/migrations.md#4-partitioning-roadmap)). | schema, ops | open |
| OQ-08 | Fine-tuning (LoRA) of company models inside the platform? | **No** in v1; models are consumed through `model-gateway` only. | scope | open |
| OQ-09 | Native SIEM formats (syslog/CEF) for audit streaming? | **Webhook (JSON, HMAC-signed) only**; customers bridge to syslog/CEF in their receiver ([spec 17 §1.2](03-specs/17-audit-usage-metering.md#12-siem-streaming)). | spec 17 | open |
| OQ-10 | Handle edited/deleted messages in Slack and Teams? | **Ignore edits and deletions** in v1; the original message is what the agent saw; the thread shows a note if the user edits. | spec 16 §3 | open |
| OQ-11 | UI languages beyond English? | **English only** in 1.0, all strings already in `next-intl` catalogues; Hindi and other Indian languages in a 1.x minor. Agents answer in the user's language regardless. | spec 19 | open |
| OQ-12 | TypeScript 7 (native compiler) or 6? | **TypeScript 7.0.2**; if any tool requires the JS compiler API, alias `typescript` to `@typescript/typescript6@6.0.3` for that package only ([stack](stack.md)). | web, CI | open |
| OQ-13 | Per-tenant point-in-time restore in the shared tier? | **Not supported**; restore to a scratch cluster and export the tenant with `scripts/dr/export_tenant.py` ([backup-dr §2.3](07-ops/backup-dr.md#23-single-tenant-restore-saas)); dedicated-tier tenants get database-level PITR. | backup-dr | open |
| OQ-14 | Visual regression testing for the web app? | **Not in v1**; component tests + Playwright + axe ([testing-strategy §5](08-quality/testing-strategy.md#5-frontend-tests)). | testing | open |
| OQ-15 | Are all version pins in stack.md current? | **Verify in M0-T02** before committing the first lockfiles (`uv lock --upgrade-package`, `pnpm outdated`, release pages); rows added late (tiktoken, pillow, pypdf, filetype, mistune, jmespath, jinja2, ClamAV, Mailpit, GreenMail, honcho) and CI scanner tools (gitleaks, osv-scanner, Trivy, Semgrep, zizmor, ZAP, squawk, kubeconform, syft, cosign) are pinned at the then-latest stable release. Record the verified versions in stack.md in the same PR. | stack, M0-T02 | open |
| OQ-16 | Multi-region SaaS with per-tenant region choice? | **One region per SaaS deployment**; `tenants.data_residency` (default `in`) records the region and must equal the deployment's region; another region = another deployment. | data-protection §7, spec 02 | open |
| OQ-17 | Default sandbox runtime: gVisor or Kata? | **gVisor** (`AR_SANDBOX_DEFAULT_RUNTIME_CLASS=gvisor`); Kata selectable per template for high-assurance tenants. | spec 12, helm-k8s §5 | open |
| OQ-18 | Should routines be creatable by the agent itself from chat? | **No**: the user turns a message into a routine through the UI action ([US-RTN-07](01-prd/08-routines.md#us-rtn-07--turn-a-chat-request-into-a-routine-p1)); no agent tool creates routines in v1. | spec 15, PRD 08 | open |
| OQ-19 | Grievance redressal endpoint in the product? | **No endpoint**; tenants configure `settings.privacy.grievance_contact` shown in the app; the product supplies export and erasure tooling ([data-protection §3](06-security/data-protection.md#3-data-principal-rights)). | data-protection | open |
| OQ-20 | Web Push / mobile push notifications? | **No** in v1 (in-app, email, Slack, Teams only). | spec 20 | open |

## Accepted risks

Recorded by M14-T07 after the security campaign (each with owner, rationale, review date). At the time of writing no risks have been accepted.

## Decision log

| Date (IST) | ID | Decision |
|---|---|---|
| 2026-10-20 | OQ-06 | Interim denial of W2/W3 between M4 and M5 confirmed as part of the plan. |
| 2026-10-20 | ADR-0009 (revised) | Product owner decision: installations are mostly in-house per company, not consumer scale. **Postgres + pgvector is the default retrieval store** for knowledge as well as memory and tool search. Retrieval stays implementation-agnostic behind the `RetrievalStore` port ([spec 10 §6](03-specs/10-knowledge.md#6-retrieval-store-port-retrievalstore)): default pgvector adapter (HNSW on `halfvec`, `tsvector` lexical signal, RRF, in-query RLS/tenant/ACL filters), optional Qdrant adapter selected by `AR_VECTOR_BACKEND=qdrant` (compose profile `qdrant`, Helm subchart disabled by default), per-collection migration path ([spec 10 §9](03-specs/10-knowledge.md#9-migrating-between-backends)) and a shared conformance suite every adapter must pass ([spec 10 §10](03-specs/10-knowledge.md#10-retrievalstore-conformance-suite)). Plan: M7-T02 (port + pgvector + suite), M7-T09 (Qdrant adapter, optional), M7-T10 (migration). Supersedes the original "Qdrant for knowledge" decision. |
