# Data protection (DPDP Act 2023 and general privacy)

The platform is deployed by a company (the **Data Fiduciary**) for its employees and approved users (**Data Principals**). In SaaS mode the operator is a **Data Processor** acting on the tenant's documented instructions. This document lists the product capabilities that let a tenant comply with India's Digital Personal Data Protection Act, 2023 and the DPDP Rules, and with similar regimes. It is not legal advice; tenant counsel decides retention periods and lawful bases.

## 1. Personal data inventory

| Data | Tables / stores | Purpose | Default retention (tenant-configurable) |
|---|---|---|---|
| Identity: name, email, IdP subject, groups, attributes (department, location, clearance, db_role) | `users`, `groups`, `group_members`, Keycloak | Authentication, authorisation | Account lifetime; deprovisioned users anonymised after 30 days (`ErasureWorkflow` optional) |
| Conversations and messages | `conversations`, `messages`, `run_*`, Valkey streams (TTL) | Service delivery | `retention.conversations_days` 365; `run_events_days` 90 |
| Files and artifacts | `files`, object storage | Service delivery | `retention.files_days` 365 |
| Memory facts | `memory_facts` | Personalisation (user-controllable) | `memory_inactive_days` 730 |
| Credentials (OAuth grants) | `credential_grants`, secrets store | Act on the user's behalf | Until disconnected/erased |
| Channel identities | `channel_identities` | Map Slack/Teams/email users | Until unlinked/erased |
| Usage | `usage_events`, `usage_daily` | Cost attribution | 400 days / 7 years aggregated |
| Audit events | `audit_events` (no message content) | Security, legal obligations | `audit_years` 7 |
| Telemetry | Tempo, Loki, Prometheus, Langfuse | Operations | No content in traces, metrics or logs; Langfuse generation content only when `settings.observability.capture_content` (default off in SaaS, on in single-tenant); user ids hashed when `AR_LOG_HASH_USER_IDS=true`; 30-day backend retention |
| Knowledge documents | `documents`, `document_chunks`, `chunk_embeddings` (or Qdrant with the optional adapter), object storage | Company knowledge; may contain personal data | Mirrors source; deleted with source |

## 2. Principles mapped to features

| Requirement | Feature |
|---|---|
| Lawful purpose and notice | Tenant-configurable notice shown at first login (`settings.branding` + notice text and version); acceptance recorded in `users.attributes.notice_version` and audit `user.notice_accepted` |
| Purpose limitation | Content is used only to serve the user; no model training on tenant data by the platform; evaluation datasets are created only by explicit builder action |
| Data minimisation | No content in telemetry/audit; memory extraction skips DPDP-sensitive categories unless explicit ([spec 11 §2](../03-specs/11-memory.md#2-rules)); PII redaction options |
| Accuracy and correction | Users edit profile (`PATCH /api/v1/me`) and memory facts; admins correct attributes |
| Storage limitation | Retention sweeps ([spec 17 §3](../03-specs/17-audit-usage-metering.md#3-retention-retentionsweepworkflow)) |
| Security safeguards | [threat-model](threat-model.md), encryption at rest (Postgres volume/TDE per infra, S3 SSE, secrets envelope encryption), TLS, RBAC, audit |
| Breach notification | Audit + alerting + incident runbook `rb-15-personal-data-breach` with tenant notification template; operator notifies tenant without undue delay (SaaS contract) |
| Data localisation / residency | `tenants.data_residency` selects the deployment region in SaaS; single-tenant installs stay on customer infrastructure; no third-party model calls (G1) |
| Processor obligations (SaaS) | Support access only via tenant grants ([authn-authz §6](authn-authz.md#6-support-access-saas)); sub-processor list is only the infrastructure the operator runs |

## 3. Data-principal rights

| Right | How |
|---|---|
| Access / summary | `GET /api/v1/me/export` produces a ZIP (profile, conversations, messages, files list + contents, memory facts, connections metadata, channel identities, usage summary) → `export_ready` notification; also `/memory` page |
| Correction and completion | Profile edit, memory edit, admin attribute edit |
| Erasure | `POST /api/v1/users/{user_id}:erase` (admin, step-up) runs `ErasureWorkflow` ([spec 02 §4](../03-specs/02-identity-tenancy.md#4-workflows-task-queue-ar-system)); users can delete conversations, files and memory themselves at any time; `DELETE /api/v1/memory` forgets everything |
| Grievance redressal | Tenant setting `settings.privacy.grievance_contact` (name, email) displayed in the app footer and notice; requests are handled by the tenant; the platform provides the export and erasure tooling |
| Nomination | Handled by the tenant's HR process; admins can act on erasure/export on behalf of a nominee |
| Withdraw consent | Disabling memory (`settings.memory_enabled=false` for the user) and disconnecting connections take effect immediately |

`settings.privacy` is part of `TenantSettings`: `{notice_text_md, notice_version, grievance_contact: {name, email}}` (defaults: empty notice, version `0`, no contact — the UI warns admins until configured).

## 4. Erasure completeness

`ErasureWorkflow` deletes, for the user: conversations they own (and messages, runs, steps, events, tool calls, approvals they requested), files they own, memory facts (`user`, `agent_user`), credential grants and personal secrets (incl. `__delegation__`), channel identities, notifications, API keys, sessions, routines are transferred or deleted per admin choice (the endpoint refuses while they own active routines/agents), retrieval entries (`RetrievalStore.delete`; `chunk_embeddings` rows or Qdrant points) of documents uploaded to personal upload sources, Langfuse traces (by hashed user id), Valkey keys. Audit events are retained but contain no content; the user row is anonymised (`email` → `erased+{id}@invalid`, `display_name` → `Erased user`) and `status='deprovisioned'`. Evidence: audit `erasure.completed` with counts.

## 5. PII handling

- Detection: Presidio analyzer with default recognisers plus Indian recognisers in `ar_domain.pii.recognizers_in`: Aadhaar (12 digits, Verhoeff checksum, not starting with 0/1), PAN (`[A-Z]{5}[0-9]{4}[A-Z]`), Indian mobile (`(\+91[\-\s]?)?[6-9]\d{9}`), UPI ID (`[\w.\-]{2,256}@[a-zA-Z]{2,64}`), IFSC (`[A-Z]{4}0[A-Z0-9]{6}`), passport, voter id (EPIC), GSTIN.
- Redaction points: tool results (per tool `data_classification` ≥ `confidential` or agent `safety.pii_masking`), delivery payloads leaving the tenant, guardrail output stage (`pii_excess`), logs (always).
- Replacement format: `<PII:TYPE>` (e.g. `<PII:AADHAAR>`), consistent within one result.
- Knowledge ingestion does **not** redact by default (documents are company records under their own ACLs); collections can enable `redact_pii` in settings.

## 6. Children's data

The platform serves employees; tenants must not onboard users under 18. No features target children.

## 7. Cross-border transfer

No content leaves the deployment region: model calls go to operator-registered endpoints; web egress is allowlisted; telemetry backends are in-region. The operator documents the region per tenant (`data_residency`).

## 8. Assurance records

Evidence items, run records, sign-offs, agent cards and disposition certificates are personal-data-bearing only to the extent the captured bytes are. They follow the retention schedule in [spec 21 §2](../03-specs/21-records-governance.md#2-legal-hold-and-retention-schedules). Legal hold stops erasure and the retention sweep for covered rows; the erasure certificate lists what was kept. Guest email addresses are identity data of an external person, retained until the guest principal is revoked and the grant retention (365 days after `expires_at`) elapses, unless a hold covers the grant's audit events. Guest sessions store no conversation content because guests cannot chat in 1.0.
