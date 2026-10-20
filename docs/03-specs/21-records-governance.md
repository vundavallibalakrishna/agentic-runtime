# Spec 21: Records, evidence, legal hold, AI governance, guests and binders (`ar_domain.records`)

Normative behaviour for the core assurance features added for any regulated buyer. Decisions: [ADR-0021](../02-architecture/adr/ADR-0021-evidence-immutability.md), [ADR-0022](../02-architecture/adr/ADR-0022-run-records.md), [ADR-0023](../02-architecture/adr/ADR-0023-pack-extensions.md), [ADR-0024](../02-architecture/adr/ADR-0024-guest-principals.md), [ADR-0025](../02-architecture/adr/ADR-0025-output-signoff.md). Tables: [schema §23–§28](../04-data/schema.md#23-evidence-vault-ar_domainrecords). Related behaviour that lives in the owning spec: content packs ([spec 05 §10](05-agent-registry.md#10-content-packs)), sign-off and segregation of duties ([spec 09 §11–§12](09-policy-approvals.md#11-reviews-and-sign-off)), strict grounding ([spec 07 §13](07-agent-runtime.md#13-strict-grounding)), run records ([spec 18 §7](18-observability-eval.md#7-run-records-and-re-performance)). The GRC solution pack uses only the extension points in §9 and never alters these tables ([10-grc-pack](../10-grc-pack/README.md)).

Request and response sketches in this spec name the Python attribute. The JSON property is the camelCase alias (`file_id` is `fileId`, `scope_query` is `scopeQuery`). See [api-conventions §3](../05-contracts/api-conventions.md#3-request-conventions).

`ar_domain.records` owns `evidence_items`, `evidence_custody_events`, `legal_holds`, `legal_hold_members`, `retention_schedules`, `disposition_certificates` and `binder_exports`. Guest tables are in `ar_domain.identity` and are created by M14-T11, not by M1. Agent cards are in `ar_domain.agents`. Run records are in `ar_domain.runs`.

## 1. Evidence vault

An evidence item is an immutable byte object plus a signed manifest. Content lives in the Object Lock bucket `AR_EVIDENCE_BUCKET` (default `ar-evidence`), key `tenants/{tenant_id}/evidence/{evidence_item_id}`. The files bucket is not used. Object Lock mode is `AR_EVIDENCE_LOCK_MODE` (`compliance` in `staging` and `prod`; `governance` allowed in `dev`). Default retain-until is `collected_at + AR_EVIDENCE_DEFAULT_LOCK_DAYS` (2555, seven years). A legal hold also sets the S3 legal-hold flag on the object; release clears that flag and does not shorten the Object Lock retention.

Manifest fields signed by the records service (Ed25519, key `AR_EVIDENCE_SIGNING_KEY`, id `AR_EVIDENCE_SIGNING_KEY_ID`): JCS of `{id, tenant_id, content_sha256, size_bytes, media_type, collected_at, source_system, collection_method, collector_principal_type, collector_principal_id, collector_run_id, collector_tool_call_id, provenance}`. `content_sha256` is hex SHA-256 of the stored bytes. The signature and `signature_key_id` are columns, not part of the signed body.

Trusted timestamping follows [OQ-25](../open-questions.md): when `tenants.settings.evidence.tsa_enabled` is true, the service requests an RFC 3161 token over `content_sha256` from `tenants.settings.evidence.tsa_url` or, if that is empty, `AR_TSA_URL`. Timeout `AR_TSA_TIMEOUT_MS`. If timestamping is enabled and the TSA does not return a valid token, capture fails (422 `tsa_unavailable`) and no row is committed. When timestamping is off (the default), `rfc3161_token` stays null. SHA-256, the service signature and Object Lock are always on.

`provenance` (`ar_contracts.records.EvidenceProvenance`) is `{source_system, query, request_sha256, source_url, tool_qualified_name, args_hash, browser_url, note}`. Secrets and raw credentials are never stored. Tool arguments are represented by `args_hash` only, matching [audit §1](../06-security/audit.md#1-properties).

Capture is one transaction: write the object (If-None-Match, content hash as checksum), insert `evidence_items` (`status='sealed'`), insert `evidence_custody_events` (`action='captured'`), audit `evidence.captured`. A crash after the object put is retried by `EvidenceCaptureWorkflow` (id `evidence-capture-{idempotency_key}`), which deletes an unreferenced object before retrying.

Updates may change only `status` (`sealed` → `disposed`), `legal_hold` and `worm_locked_until`. The trigger `evidence_items_immutable` rejects every other column change and every delete. Disposal is §5.

### 1.1 Built-in tools

Registered as the platform MCP server `records` (in-process in `mcp-gateway`, same lifecycle as the other built-ins in [spec 08 §9](08-tool-registry-mcp.md#9-built-in-tool-schemas-platform-servers-executed-in-process-by-mcp-gateway-unless-noted)):

| Tool | Risk | Behaviour |
|---|---|---|
| `records.capture` | R1 | Body `{bytes_file_id \| text, media_type, source_system, collection_method, provenance}`. Reads bytes from `files` when `bytes_file_id` is set (the caller must be allowed to read that file). Returns `{evidence_item_id, content_sha256}`. Used by routines and by the browser path below. |
| `records.get` | R0 | Metadata and verification summary for one id the run's user can read. Does not return bytes to the model; the model receives `{evidence_item_id, content_sha256, media_type, source_system, collected_at}`. |
| `records.verify` | R0 | Runs §1.2 and returns the check list. |

`browser.screenshot` ([stream-events](../05-contracts/stream-events.md)) stays a run event. It becomes evidence only when the agent or a routine calls `records.capture` with that `file_id` and `collection_method='browser_screenshot'`. The provenance stores `browser_url` and the `tool_call_id` of the screenshot.

### 1.2 Verification

`POST /api/v1/evidence/{evidence_item_id}:verify` recomputes SHA-256 from the object, checks the Ed25519 signature, checks Object Lock retention is in the future or the object is under S3 legal hold, and, when a token is present, validates the RFC 3161 token against the stored hash. Response `{valid: bool, checks: [{name, ok, detail}]}`. Writes custody `verified` and audit `evidence.verified`. A failed check returns 200 with `valid: false` (the row exists); a missing row is 404.

### 1.3 API

Permission `evidence:read` reads metadata. Permission `evidence:capture` creates. Permission `evidence:export` downloads bytes and builds exports. Object-level: the capturing principal, holders of `evidence:read`, and a guest whose grant lists the item. Guests never call `records.*` tools ([OQ-26](../open-questions.md)).

#### GET /api/v1/evidence
`evidence:read`. Query `source_system`, `collection_method`, `from`, `to`, `q` (matches `source_system` and provenance note). Item `EvidenceSummary {id, content_sha256, size_bytes, media_type, source_system, collection_method, collected_at, legal_hold, status}`.

#### POST /api/v1/evidence
`evidence:capture`. Header `Idempotency-Key`. Multipart bytes or `{file_id, media_type, source_system, collection_method, provenance}`. Response `EvidenceItem` (summary plus `signature_key_id`, `worm_locked_until`, `rfc3161: bool`, collector ids). Audit `evidence.captured`.

#### GET /api/v1/evidence/{evidence_item_id}
`evidence:read` or object-level. Metadata only. Does not write custody.

#### GET /api/v1/evidence/{evidence_item_id}/content
`evidence:export` or a guest grant that includes the item. Streams the bytes. Guests receive a watermarked rendition (§7.3) when the media type is PDF, PNG or JPEG; other types are refused to guests with 415 `watermark_unsupported`. Writes custody `accessed` and audit `evidence.accessed` (detail: `watermarked: bool`). Support-access `metadata` grants do not pass this route (404), same rule as other content routes ([authn-authz §6](../06-security/authn-authz.md#6-support-access-saas)).

#### POST /api/v1/evidence/{evidence_item_id}:verify
`evidence:read`. See §1.2.

#### GET /api/v1/evidence/{evidence_item_id}/custody
`evidence:read`. Append-only custody rows `{id, action, actor_principal_type, actor_principal_id, detail, audit_event_id, created_at}`.

## 2. Legal hold and retention schedules

A legal hold is a matter. Creating one evaluates `scope_query` (`ar_contracts.records.HoldScope`: `{record_classes: [...], custodian_user_ids: [...], from, to, evidence_ids: [...], conversation_ids: [...]}`) and inserts `legal_hold_members` for every match. Covered classes: `conversation`, `run`, `run_record`, `evidence_item`, `document`, `file`, `memory_fact`, `signoff`, `agent_card`, `audit_archive`. Membership insert sets the denormalised flag the existing sweep already honours: `conversations.retention_class='legal_hold'` (previous class stored on the member row as `detail.previous_retention_class`), `files` legal-hold marker used by [spec 17 §3](17-audit-usage-metering.md#3-retention-retentionsweepworkflow), `evidence_items.legal_hold=true`, and the S3 legal-hold flag. Release restores the previous conversation class only when no other active hold still covers the row.

`RetentionSweepWorkflow` and `ErasureWorkflow` skip any row that is a member of an active hold. Erasure completion detail lists `held_record_ids` that were kept. Audit archive objects under hold are not purged.

Retention schedules are rows in `retention_schedules`, seeded per tenant by `seed_tenant_defaults` from this table (tenants override with `retention:manage`):

| `record_class` | Default retain | Disposition |
|---|---|---|
| `conversation` | `retention.conversations_days` (365) | `delete` |
| `run` | same as the parent conversation | `delete` |
| `run_record` | 2555 days | `archive_then_delete` |
| `evidence_item` | 2555 days | `archive_then_delete` |
| `file` | `retention.files_days` (365) | `delete` |
| `memory_fact` | `memory_inactive_days` (730) | `delete` |
| `signoff` | 2555 days | `archive_then_delete` |
| `agent_card` | life of the agent plus 2555 days | `archive_then_delete` |
| `cert_in_log` | 180 days | `delete` |
| `audit_archive` | `audit_years` (7) × 365 days | keep in the Object Lock archive; no delete before that |
| `guest_grant` | `expires_at` plus 365 days | `delete` |

`archive_then_delete` copies the manifest and bytes to `AR_AUDIT_ARCHIVE_BUCKET` under `retention/{tenant_id}/{record_class}/{id}`, verifies the copy, then deletes the live row only when no hold applies. Every disposition inserts an append-only `disposition_certificates` row `{record_class, record_id, content_sha256, method, disposed_at, certificate_hash}` and audits `evidence.disposed` or `disposition.certified` (`evidence.disposed` for evidence items; `disposition.certified` for every class including evidence). `certificate_hash` is SHA-256 of JCS of the certificate body without that field.

Platform minimums: `evidence_item`, `run_record`, `signoff` and `audit_archive` cannot be set below 180 days (422 `retention_below_minimum`). `cert_in_log` cannot be set below 180 days.

#### GET /api/v1/legal-holds
`holds:manage`. Item `LegalHold {id, matter, status, custodians, scope_query, started_at, released_at, approver}`.

#### POST /api/v1/legal-holds
`holds:manage`. Step-up. Body `{matter, custodians: [user_id], scope_query, approver_user_id}`. The approver must hold `holds:manage` and must not be the caller (two-person). Response includes `member_count`. Audit `legal_hold.created`. Outbox `legal_hold.created`.

#### GET /api/v1/legal-holds/{hold_id}
`holds:manage`. Adds `members` page `{record_class, record_id, applied_at}`.

#### POST /api/v1/legal-holds/{hold_id}:release
`holds:manage`. Step-up. Body `{reason}`. Caller must not be the user who created the hold. Audit `legal_hold.released`.

#### GET /api/v1/retention-schedules
`retention:manage` or `audit:read`. One row per class, with `effective_days` after applying the minimums.

#### PUT /api/v1/retention-schedules/{record_class}
`retention:manage`. Body `{retention_days, disposition}`. Audit `retention_schedule.updated`. Does not shorten Object Lock already applied to existing objects.

#### GET /api/v1/disposition-certificates
`audit:read`. Query `record_class`, `from`, `to`.

#### GET /api/v1/disposition-certificates/{certificate_id}
`audit:read`.

## 3. AI governance register

On every successful publish ([spec 05](05-agent-registry.md)), `agents.service` inserts an `agent_cards` row for that `agent_version_id`. The card is the platform's record of its own agent: purpose, data categories, oversight mode, and review date. Systems the customer runs outside this platform are pack data, not this table.

Card body (`ar_contracts.records.AgentCard`): `{purpose, risk_tier, data_categories, oversight_mode, eval_summary, known_limitations, owner_user_id, review_due_at}`. `purpose` defaults to the agent description. `oversight_mode` is `autonomous_r0` when the resolved tools are only R0/R1, `approval` when any tool is W2/W3, else `human_in_loop`. `eval_summary` is the latest gated eval for that version or null. `card_hash` is SHA-256 of JCS of the body. The row is immutable except `known_limitations`, `review_due_at` and `data_categories` (audit `agent_card.updated` with a diff). Publish audits `agent_card.published` and emits `agent_card.published`.

`ai_oversight_daily` is filled by `UsageRollupWorkflow` from approvals and sign-offs for that agent: `approvals_requested`, `approvals_approved`, `approvals_rejected`, `signoffs_approved`, `signoffs_rejected`, `overrides` (decisions where the human edited arguments or rejected).

`ai_incidents` records a suspected model or agent failure: `{agent_id, agent_version_id, run_id, severity: low|medium|high, summary, status: open|mitigated|closed}`. Creating one audits `ai_incident.created` and emits `ai_incident.opened`.

#### GET /api/v1/agent-cards
`ai_governance:read`. Query `agent_id`, `risk_tier`, `review_due_before`.

#### GET /api/v1/agents/{agent_id}/cards
`ai_governance:read` or an editor of the agent. Items are one card per published version.

#### GET /api/v1/agents/{agent_id}/cards/{version}
Same readers. `version` is the integer agent version.

#### PATCH /api/v1/agents/{agent_id}/cards/{version}
`ai_governance:manage`. Body `{known_limitations?, review_due_at?, data_categories?}`. Refuses any other field (422).

#### GET /api/v1/ai-incidents
`ai_governance:read`. Query `status`, `agent_id`, `severity`.

#### POST /api/v1/ai-incidents
`ai_governance:manage`. Body `{agent_id, agent_version_id?, run_id?, severity, summary}`.

#### PATCH /api/v1/ai-incidents/{incident_id}
`ai_governance:manage`. Body `{status?, summary?, severity?}`. Audit `ai_incident.updated`.

#### GET /api/v1/ai-governance/oversight
`ai_governance:read`. Query `agent_id`, `from`, `to`. Returns `ai_oversight_daily` rows.

#### POST /api/v1/ai-governance:export
`ai_governance:read`. Body `{agent_ids?: [...]}`. Builds a binder (§8) containing cards, oversight rows, linked eval summaries and incident rows. Response `202 {binder_id}`. Audit `ai_governance.exported`.

## 4. Guest principals

A guest is not a `users` row and is not a Keycloak user ([ADR-0024](../02-architecture/adr/ADR-0024-guest-principals.md)). M1 identity tables are unchanged. Guests authenticate with a magic link plus TOTP, or with a federated IdP the tenant has marked `allow_guests` on the identity provider config. They receive a session whose `principal_type` is `guest`. In 1.0 a guest cannot start a run, call a tool, or open chat ([OQ-26](../open-questions.md)). API routes other than the guest auth routes, the granted record reads, and the pack portal routes registered for guests return 403 `guest_forbidden`.

Invitation (`POST /api/v1/guests`) creates `guest_principals` (`status='invited'`, `kind` `external` | `partner` | `other`) and emails a magic link (TTL `AR_GUEST_MAGIC_LINK_TTL_S`, 900 s) stored as a hash on `guest_login_challenges`. The guest sets TOTP on first session (`POST /api/v1/auth/guest/totp/enroll`); the TOTP secret is a personal secret ref, never a column. Session TTL `AR_GUEST_SESSION_TTL_S` (28800). `expires_at` on the principal is at most `AR_GUEST_MAX_TTL_DAYS` (90) from invitation. After `expires_at`, login fails and grants are inert.

A `guest_grants` row is `{portal, scope, expiresAt, watermark}` in JSON. `portal` is `records` in core (read granted evidence and binders). Packs register further portal names through §6. `scope` is `{evidenceIds, binderIds, packRecordIds}` where `packRecordIds` is an opaque list the pack interprets. Core enforces `evidenceIds` and `binderIds` only. Columns stay `expires_at`, `evidence_ids`, `binder_ids`, `pack_record_ids`.

Every guest request audits `guest.access` with the route and grant id, in addition to the resource audit (`evidence.accessed`, `binder.downloaded`). A download also audits `guest.downloaded` with the resource id.

### 4.1 Watermark

Downloads by a guest of PDF, PNG or JPEG are rewritten with a footer (PDF) or a visible band (images) containing the guest email, tenant slug and UTC timestamp. The original evidence object is never modified; the watermarked bytes are generated per download and are not stored. Failure to watermark fails the download (500) rather than sending the original.

#### GET /api/v1/guests
`guests:manage`.

#### POST /api/v1/guests
`guests:invite`. Body `{email, display_name, kind, auth_method: magic_link_totp|federated, expires_at, grants: [{portal, scope, expires_at, watermark}]}`. Audit `guest.invited`. Email is the notification, not an in-app row (the guest has no user id).

#### GET /api/v1/guests/{guest_id}
`guests:manage`.

#### POST /api/v1/guests/{guest_id}:revoke
`guests:manage`. Sets `status='revoked'`, deletes sessions, audits `guest.revoked`.

#### POST /api/v1/guests/{guest_id}/grants
`guests:manage`. Body `{portal, scope, expires_at, watermark}`. Audit `guest.grant_created`.

#### DELETE /api/v1/guests/{guest_id}/grants/{grant_id}
`guests:manage`. Audit `guest.grant_revoked`.

#### POST /api/v1/auth/guest/request-link
Public, rate-limited (5 per email per hour). Body `{email, tenant_slug}`. Always 202 (no account enumeration). Sends a link only when an active, unexpired guest exists.

#### POST /api/v1/auth/guest/session
Public. Body `{token, totp}`. Issues the guest session cookie `ar_guest_session` (HttpOnly, Secure, SameSite=Lax, path `/guest`). Audit `guest.login` or `guest.login_failed`.

#### POST /api/v1/auth/guest/totp/enroll
Guest session that has not enrolled. Returns the otpauth URI once. The secret is stored as a secret ref.

## 5. Binder export

A binder is a ZIP of selected records. Layout:

```text
manifest.json          # JCS, sha256 of every file, signer, created_at
verify_binder.py       # stdlib-only checker: recompute hashes, print mismatches
index.pdf              # human index
index.xlsx             # one sheet per record class
records/{class}/{id}.json
evidence/{id}.bin      # raw bytes, not watermarked (callers are employees)
signoffs/{id}.json
audit/{id}.json        # audit excerpts for the selected ids, no message content
```

`manifest.json` includes `manifest_sha256` of itself without that field, and the records-service signature over that hash. `verify_binder.py` checks hashes only (no network). Signature check is documented in the script's header and performed by `POST /api/v1/evidence` verification logic when the operator runs `python verify_binder.py --public-key`.

Scheduled reports: a routine delivery target may set `reviewBeforeSend: true` ([spec 15 §4](15-routines-triggers.md) addition in §10 below). The runtime then creates a review item ([spec 09 §11](09-policy-approvals.md#11-reviews-and-sign-off)) on the binder and does not deliver until the item is `signed`.

Selection caps: `AR_BINDER_MAX_ITEMS` (5000) across classes. Over the cap → 422 `binder_too_large`.

#### GET /api/v1/binders
`binders:export` or the creator.

#### POST /api/v1/binders
`binders:export`. Body `{title, selection: {evidence_ids, run_record_ids, signoff_ids, agent_card_ids, audit_from, audit_to}, require_review: bool}`. Creates `status='draft'`. Audit `binder.created`.

#### GET /api/v1/binders/{binder_id}
Creator, `binders:export`, or a guest grant listing the binder (metadata only until download).

#### POST /api/v1/binders/{binder_id}:build
`binders:export`. If `require_review`, the binder must be `signed` or the response is 409 `review_required` and a review item is opened when one does not exist. Starts `BinderBuildWorkflow` (id `binder-{binder_id}`). Response `202`. On success `status='ready'`, audit `binder.built`, outbox `binder.ready`.

#### GET /api/v1/binders/{binder_id}/download
Creator or `binders:export` or a guest grant. Guest downloads are watermarked on the PDF and any PNG/JPEG inside the ZIP; `manifest.json` records `watermarked_for`. Audit `binder.downloaded`.

## 6. Pack extension points

Core does not import pack packages. M14-T13 adds an import-linter contract `packs-not-in-core`: every project under `libs/` and `services/` forbids `ar_pack_*`. Packs live in `packs/<pack_id>/` (package `ar_pack_<pack_id>`), an optional uv workspace member. Enabling a pack for a tenant is data, not a deploy of new core code. Installing the pack's code is an operator action (the image contains the pack, or it does not).

The six hooks:

1. **HTTP mount.** `ar_api.plugins.mount(pack_id, router)` attaches the pack router at `/api/v1/ext/{pack_id}`. Core reserves that prefix. The GRC pack's routes are specified in [10-grc-pack/api.md](../10-grc-pack/api.md).
2. **Alembic helper.** `ar_domain.packs.alembic_env(pack_id, schema)` builds an environment whose version table is `{schema}_alembic_version` and whose `target_metadata` is only the pack's models. Core keeps one linear history ([migrations §6](../04-data/migrations.md#6-pack-schemas), [OQ-28](../open-questions.md)).
3. **Permission registration.** `register_pack_permissions(pack_id, keys)` adds keys to the runtime catalogue. Keys are `{pack_id}.{resource}:{verb}` (the GRC pack uses the `grc.` prefix). They are not part of the M1 seed. `tenant_admin` includes them once the pack is enabled. The GRC list is [authn-authz §9](../06-security/authn-authz.md#9-permissions-added-after-the-m1-baseline).
4. **Audit registration.** `register_pack_audit_actions(pack_id, actions)` adds actions. Names are `{pack_id}.{resource}.{verb}`. Unknown actions still fail closed.
5. **Web nav slot.** The shell reads `GET /api/v1/tenant/packs` and renders an item per enabled pack using the pack's `nav` manifest (`{slot, href, label, permission}`). The GRC pack's pages live at `/grc/*` inside the pack's route group. Core does not link to `/grc` unless the pack is enabled.
6. **Enable flag.** `tenant_pack_flags`. Routes, tools and nav of a disabled pack return 404. Data is kept.

Content-pack install, upgrade and uninstall semantics are [spec 05 §10](05-agent-registry.md#10-content-packs). A solution pack is a content pack whose manifest `extension` block names the schema, mount, permissions, audit actions, `configSchema`, and `ui` slots. The full framework, including the testing kit, is [extension-framework](../05-contracts/extension-framework.md). Signature verification is part of install. Core does not contain industry routes, industry tables, or industry settings.

#### GET /api/v1/tenant/packs
Any signed-in principal. Items `{pack_id, version, enabled, nav}` for packs installed on the tenant. `nav` is omitted when the caller lacks the pack's read permission.

#### POST /api/v1/tenant/packs/{pack_id}:enable
`packs:manage`. The pack must be installed. Audit `tenant_pack.enabled`.

#### POST /api/v1/tenant/packs/{pack_id}:disable
`packs:manage`. Audit `tenant_pack.disabled`. Does not drop schema.

## 7. Workflows (queue `ar-system`)

| Workflow | Id | Task |
|---|---|---|
| `EvidenceCaptureWorkflow` | `evidence-capture-{idempotency_key}` | M14-T08 |
| `RetentionScheduleWorkflow` | child of `retention-{tenant_id}-{date}` | M14-T09 |
| `BinderBuildWorkflow` | `binder-{binder_id}` | M14-T12 |
| `RunRecordSealWorkflow` | `run-record-{run_id}` | M13-T07, defined in [spec 18 §7](18-observability-eval.md#7-run-records-and-re-performance) |

## 8. Configuration

| Variable | Default | Role |
|---|---|---|
| `AR_EVIDENCE_BUCKET` | `ar-evidence` | Object Lock bucket |
| `AR_EVIDENCE_LOCK_MODE` | `compliance` | `compliance` or `governance` |
| `AR_EVIDENCE_DEFAULT_LOCK_DAYS` | `2555` | Retain-until for new objects |
| `AR_EVIDENCE_SIGNING_KEY` | (secret) | Ed25519 PEM |
| `AR_EVIDENCE_SIGNING_KEY_ID` | `evidence-k1` | `signature_key_id` |
| `AR_TSA_URL` | empty | Platform TSA used when the tenant enables timestamping without its own URL |
| `AR_TSA_TIMEOUT_MS` | `2000` | TSA call timeout |
| `AR_RUN_RECORD_MAX_BLOB_BYTES` | `52428800` | Max encrypted tool I/O blob |
| `AR_GUEST_MAGIC_LINK_TTL_S` | `900` | Magic link lifetime |
| `AR_GUEST_SESSION_TTL_S` | `28800` | Guest session |
| `AR_GUEST_MAX_TTL_DAYS` | `90` | Longest guest principal lifetime |
| `AR_BINDER_MAX_ITEMS` | `5000` | Selection cap |
| `AR_PACK_SIGNATURE_REQUIRED` | `true` (`false` when `AR_ENV=dev`) | Reject unsigned content packs |
| `AR_PACK_TRUSTED_KEYS` | (secret JSON) | Array of `{key_id, public_key_pem}` |
| `AR_PACKS_DIR` | `packs` | Workspace directory scanned at startup |
| `AR_GROUNDING_MAX_SENTENCES` | `200` | Cap per answer in [spec 07 §13](07-agent-runtime.md#13-strict-grounding) |

Tenant settings added to `TenantSettings` (not env vars): `evidence.tsa_enabled` (bool, default false), `evidence.tsa_url` (string, default empty), `security.require_step_up_for_signoff` (bool, default true).

## 9. Metrics

`ar_evidence_captured_total{source_system}`, `ar_evidence_verify_total{result}`, `ar_legal_holds_active`, `ar_retention_disposed_total{record_class}`, `ar_guest_logins_total{result}`, `ar_binder_build_seconds`, `ar_pack_enabled{pack_id}`.

## 10. Routine delivery review

Additive rule for [spec 15 §4](15-routines-triggers.md#4-delivery-phase-in-agentrunworkflow-for-triggerroutine): a delivery target object may include `reviewBeforeSend: bool` (default false; Python attribute `review_before_send`). When true, `AgentRunWorkflow` writes a binder of the delivery body (one evidence item for the rendered body, one binder) and a review item, and does not call `delivery.*` until the review item is `signed`. Rejection notifies the routine owner (`review_decided`) and skips delivery. This is the review step for scheduled reports.

## 11. Test plan

- Unit: manifest JCS and signature known-answer; RFC 3161 token fixture (valid and hash mismatch); watermark text present; guest route denylist; retention minimums; hold membership query per class.
- Integration: capture → verify → tamper object as `ar_owner` → verify `valid: false`; hold blocks sweep and erasure; release restores `retention_class`; binder ZIP round-trip through `verify_binder.py`; guest cannot `POST /api/v1/conversations`; cross-tenant 404 on every new id route.
- Temporal: capture retry after a simulated object-store failure; binder build; review-before-send does not deliver before sign-off.
- Security: metadata support grant receives 404 on `/content` and binder download; watermark failure does not fall back to the original bytes.
