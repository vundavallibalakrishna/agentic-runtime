# M14 — Security hardening & compliance

Goal: production-grade safety and compliance. Input/output guardrails, prompt-injection defences, PII redaction, retention, DPDP data-principal rights (access, correction, erasure, grievance), audit export and SIEM streaming, support-access controls, security testing and fixes.

Exit criteria: the threat-model verification table ([threat-model §4](../06-security/threat-model.md#4-verification)) is all green; red-team suite pass rate ≥ the gate; erasure of a user removes all personal content within 24 h and is evidenced in audit; ZAP baseline and dependency scans have no high findings.

M14-T08 through M14-T13 are required for 1.0. M14-T07 may run before them; M15-T07 waits for all six.

---

### M14-T01 · Guardrails, injection classifier, PII redaction
- **Depends on:** M13-T04
- **Areas:** `ar_runtime/guardrails.py`, `ar_mcp_gateway/{redaction.py,injection.py}`, `ar_domain/pii/{analyzer.py,recognizers_in.py}`, prompts `injection_classifier.md`, `guardrail_input.md`, `guardrail_output.md`
- **Spec:** [prompt-injection](../06-security/prompt-injection.md), [data-protection §5](../06-security/data-protection.md#5-pii-handling), [spec 08 §5](../03-specs/08-tool-registry-mcp.md#5-execution-pipeline-post-internalv1tool-callsexecute)
- **Do:** Input/output guardrails (tenant feature `guardrails`; aliases `AR_GUARDRAIL_INPUT_ALIAS`, `AR_GUARDRAIL_OUTPUT_ALIAS`; categories and actions per prompt-injection §4), injection classifier on open-world results (`AR_INJECTION_CLASSIFIER_TIMEOUT_MS`, fail-open with metric), Presidio-based PII redaction with Indian recognisers (Aadhaar with Verhoeff check, PAN, Indian mobile, UPI ID, IFSC) applied per tool `redact_pii` setting and tenant `pii_redaction`, markdown image/link exfiltration filter in rendered output (prompt-injection §6).
- **Done when:** red-team corpus categories "injection via tool output", "exfiltration via image" pass; PII recognisers ≥ 0.95 precision on the fixture set.
- **Tests:** unit (recognisers with valid/invalid checksums), eval red-team suite run in CI nightly, rendering exfil tests (Vitest + backend).

### M14-T02 · Retention, erasure and data-principal rights
- **Depends on:** M14-T01
- **Areas:** `ar_system/workflows/{retention_sweep.py,erasure.py}`, `ar_api/routers/{me.py,users.py}`, `ar_domain/identity/data_rights.py`
- **Spec:** [spec 17 §3](../03-specs/17-audit-usage-metering.md#3-retention-retentionsweepworkflow), [spec 02 §4](../03-specs/02-identity-tenancy.md#4-workflows-task-queue-ar-system), [data-protection](../06-security/data-protection.md)
- **Do:** `RetentionSweepWorkflow` implementing every row of spec 17 §3 (batched, audited `retention.swept`, audit purge via `purge_audit_events` after export); `ErasureWorkflow` (conversations, messages, files, memory, credential grants, channel identities, retrieval-store entries of documents the user uploaded (via `RetrievalStore.delete`), Langfuse traces by user id hash) with completion evidence `erasure.completed`; `GET /api/v1/me/export` (async export ZIP of the user's data → `export_ready` notification) and `POST /api/v1/users/{user_id}:erase`; consent/notice version recording on first login (users.attributes.notice_version) per data-protection §3.
- **Done when:** erasure test verifies zero rows/objects/points remain for the user (except audit events, which hold no content).
- **Tests:** Temporal tests per retention rule (time-machine); erasure completeness test across Postgres (incl. `chunk_embeddings`), S3, and Qdrant in the `conformance-qdrant` job.

### M14-T03 · Audit export, SIEM streaming and nightly verification
- **Depends on:** M14-T02
- **Areas:** `ar_system/workflows/audit_export.py`, `ar_system/subscribers/webhooks.py`, `ar_api/routers/audit.py`
- **Spec:** [spec 17 §1.2–1.4](../03-specs/17-audit-usage-metering.md#12-siem-streaming), [audit](../06-security/audit.md)
- **Do:** `POST /api/v1/audit-exports`, `GET /api/v1/audit-exports/{export_id}`; `AuditExportWorkflow` (gzip JSONL/CSV, verification while exporting, Object Lock archive bucket `AR_AUDIT_ARCHIVE_BUCKET` for retention/tenant deletion); SIEM streaming via outbox `audit.event` → tenant webhook configured in `settings.audit.siem` (signed, batched); nightly chain verification per tenant → `ARAuditChainBroken` metric.
- **Done when:** an export of 1 M rows completes with constant memory; tampering triggers the alert.
- **Tests:** Temporal export test; SIEM delivery test; verification alert test.

### M14-T04 · Session, transport and HTTP hardening
- **Depends on:** M14-T01
- **Areas:** `ar_api/middleware/security_headers.py`, `apps/web/next.config.ts` (headers), `ar_common/web/middleware.py`, Keycloak realm settings
- **Spec:** [authn-authz §7](../06-security/authn-authz.md#7-session-and-transport-security), [threat-model](../06-security/threat-model.md)
- **Do:** Security headers (CSP with nonces for the web app, HSTS, frame-ancestors, referrer policy, permissions policy), cookie flags review, session fixation protection on login, step-up coverage for all sensitive actions listed in authn-authz §5, brute-force and rate limits on auth endpoints, SSRF guard library used by every outbound fetch (webhooks, web.fetch, OpenAPI base URLs, model providers), upload limits.
- **Done when:** ZAP baseline scan in CI has no high/medium findings; SSRF test matrix (IPv4/IPv6/private/link-local/DNS rebinding/redirect) passes.
- **Tests:** SSRF matrix tests; header snapshot tests; CI ZAP job.

### M14-T05 · Secrets, keys and supply-chain hardening
- **Depends on:** M14-T04
- **Areas:** `ar_domain/secrets/rotation.py`, `.github/workflows/security.yml`, `images/*`
- **Spec:** [secrets](../06-security/secrets.md), [ci-cd §5](../07-ops/ci-cd.md#5-security-scanning)
- **Do:** Internal JWT key rotation (two active keys, JWKS overlap), KEK rotation for `db_encrypted` with re-wrap job, session/cursor/token-cache key rotation procedures, gitleaks, pip-audit, pnpm audit, Trivy image scan, SBOM attestation, cosign verification policy example for clusters.
- **Done when:** key rotation runbooks executed in a test without downtime; scans gate merges on high severity.
- **Tests:** rotation integration tests; CI security job.

### M14-T06 · Support access enforcement and admin safety
- **Depends on:** M14-T04
- **Areas:** `ar_api/principal.py`, `ar_api/deps.py`, `ar_domain/identity/support.py`
- **Spec:** [authn-authz §6](../06-security/authn-authz.md#6-support-access-saas), [spec 02 §3.11](../03-specs/02-identity-tenancy.md#311-support-access-saas-mode-only)
- **Do:** Enforce `metadata` vs `content` grant levels at the service layer (content endpoints check `principal.can_read_content`), banner in UI during support sessions, automatic session end on expiry/revocation, audit of every request under a grant, `ar_readonly` break-glass procedure documented and audited.
- **Done when:** a platform admin with `metadata` grant receives 404 on message, file content and tool-result endpoints.
- **Tests:** table-driven tests over content endpoints; expiry test.

### M14-T07 · Security test campaign and fixes
- **Depends on:** M14-T03, M14-T05, M14-T06
- **Areas:** `tests/security/**`, `evals/redteam/**`, findings fixes across the codebase
- **Spec:** [threat-model §4](../06-security/threat-model.md#4-verification), [testing-strategy §7](../08-quality/testing-strategy.md#7-security-tests)
- **Do:** Run the full security suite (cross-tenant generator over all routes, RLS, IDOR, approval bypass attempts, sandbox escape attempts on gVisor, egress bypass, prompt-injection red-team, auth flows), record results in `docs/06-security/verification-log.md` (created by this task), fix all high/critical findings, document accepted risks in open-questions.
- **Done when:** threat-model verification table all green with links to tests.
- **Tests:** the campaign suites in CI (nightly for slow ones).

### M14-T08 · Evidence vault
- **Depends on:** M14-T03
- **Areas:** `ar_domain/records/{models.py,repository.py,service.py,verify.py}`, `ar_system/workflows/evidence_capture.py`, `ar_api/routers/evidence.py`, `mcp-gateway` built-in `records`, migration `0024_evidence_vault`
- **Spec:** [spec 21 §1](../03-specs/21-records-governance.md#1-evidence-vault), [schema §23](../04-data/schema.md#23-evidence-vault-ar_domainrecords), [ADR-0021](../02-architecture/adr/ADR-0021-evidence-immutability.md)
- **Do:** Tables `evidence_items` and `evidence_custody_events`, trigger `evidence_items_immutable`, and `fk_run_records_evidence` (the run-record tables already exist from M13-T07's revision 0023). Bucket `AR_EVIDENCE_BUCKET`, Object Lock mode `AR_EVIDENCE_LOCK_MODE`, retain `AR_EVIDENCE_DEFAULT_LOCK_DAYS`. Ed25519 manifest signature. Optional RFC 3161 per [OQ-25](../open-questions.md). `EvidenceCaptureWorkflow` id `evidence-capture-{idempotency_key}`. Tools `records.capture` (R1), `records.get` (R0), `records.verify` (R0). Browser screenshots become evidence only through `records.capture` with `collection_method=browser_screenshot`. Endpoints in spec 21 §1.
- **Done when:** a captured object verifies; a content-column update is rejected by the trigger; a failed TSA when timestamping is enabled rolls the capture back.
- **Tests:** signature known-answer; immutability trigger; workflow retry after a crash between put and insert; cross-tenant 404.

### M14-T09 · Legal hold and retention schedules
- **Depends on:** M14-T02, M14-T08
- **Areas:** `ar_domain/records/{holds.py,retention.py}`, `ar_system/workflows/retention_schedule.py`, `ar_api/routers/{legal_holds.py,retention.py}`, migration `0025_legal_hold_retention`, `apps/web` admin pages for holds and retention
- **Spec:** [spec 21 §2](../03-specs/21-records-governance.md#2-legal-hold-and-retention-schedules), [spec 17 §7](../03-specs/17-audit-usage-metering.md), [schema §24](../04-data/schema.md#24-legal-hold-and-retention-ar_domainrecords)
- **Do:** Tables `legal_holds`, `legal_hold_members`, `retention_schedules`, `disposition_certificates`. Create and release are two-person and require step-up. A hold sets `conversations.retention_class='legal_hold'` and stores the previous class on the member; release restores it when no other hold covers the row. Retention sweep and `ErasureWorkflow` skip held rows and record `held_record_ids`. Minimum 180 days for `evidence_item`, `run_record`, `signoff`, `audit_archive` and `cert_in_log`. `archive_then_delete` copies to `AR_AUDIT_ARCHIVE_BUCKET` under `retention/{tenant_id}/{record_class}/{id}`.
- **Done when:** a held conversation is not erased; disposition certificates are append-only; a schedule below the minimum returns 422 `retention_below_minimum`.
- **Tests:** two-person create and release; sweep skip; erasure detail; certificate immutability.

### M14-T10 · AI governance register
- **Depends on:** M13-T04
- **Areas:** `ar_domain/agents/{cards.py,incidents.py}`, `ar_system` subscriber on `UsageRollupWorkflow`, `ar_api/routers/ai_governance.py`, migration `0026_ai_governance`, `apps/web` `/admin/ai-governance`
- **Spec:** [spec 21 §3](../03-specs/21-records-governance.md#3-ai-governance-register), [schema §25](../04-data/schema.md#25-ai-governance-register-ar_domainagents)
- **Do:** Tables `agent_cards`, `ai_incidents`, `ai_oversight_daily`. One card per published agent version. Updates may change only `known_limitations`, `review_due_at`, `data_categories` and `card_hash`. `oversight_mode` is `autonomous_r0`, `approval` or `human_in_loop`. `UsageRollupWorkflow` fills `ai_oversight_daily`. External AI systems are not rows in these tables. Endpoints for cards, incidents, oversight and `:export`.
- **Done when:** publishing an agent version writes one card; a second publish of the same version does not insert another; export returns a binder id.
- **Tests:** limited-update trigger or service rule; rollup; export audit `ai_governance.exported`.

### M14-T11 · External guest principals
- **Depends on:** M14-T06
- **Areas:** `ar_domain/identity/guests.py`, `ar_api/routers/{guests.py,guest_auth.py}`, `apps/web/src/app/guest/**`, migration `0027_guest_principals`
- **Spec:** [spec 21 §4](../03-specs/21-records-governance.md#4-guest-principals), [spec 02 §10](../03-specs/02-identity-tenancy.md), [schema §26](../04-data/schema.md#26-guest-principals-ar_domainidentity), [ADR-0024](../02-architecture/adr/ADR-0024-guest-principals.md), [OQ-26](../open-questions.md)
- **Do:** Tables `guest_principals`, `guest_grants`, `guest_login_challenges`. Guests are not `users` and not Keycloak users. Cookie `ar_guest_session`. Magic link plus TOTP (secret is a secret ref). Core portal `records`. Scope `{evidence_ids, binder_ids, pack_record_ids}`. Watermark PDF, PNG and JPEG, fail closed. Guest route denylist: no chat, no tools. Audit `guest.access` on every request and `guest.downloaded` on downloads. Max TTL `AR_GUEST_MAX_TTL_DAYS` (90). `POST /api/v1/auth/guest/request-link` always returns 202. This migration is not part of M1.
- **Done when:** a guest can read only granted evidence; a chat route returns 403 `guest_forbidden`; a watermark failure does not send the original bytes.
- **Tests:** login, TOTP, expiry, denylist, watermark, public request-link 202, cross-tenant 404.

### M14-T12 · Binder export
- **Depends on:** M14-T08, M5-T08
- **Areas:** `ar_domain/records/binders.py`, `ar_system/workflows/binder_build.py`, `scripts/verify_binder.py`, `ar_api/routers/binders.py`, migration `0028_binder_exports`
- **Spec:** [spec 21 §5](../03-specs/21-records-governance.md#5-binder-export), [spec 21 §10](../03-specs/21-records-governance.md#10-routine-delivery-review), [schema §27](../04-data/schema.md#27-binder-exports-ar_domainrecords)
- **Do:** Table `binder_exports`. `BinderBuildWorkflow` id `binder-{binder_id}`. ZIP contains `manifest.json`, `index.pdf`, `index.xlsx`, record metadata, evidence bytes, sign-offs and audit excerpts. `scripts/verify_binder.py` uses the Python standard library only. `files.kind` stays `export`. Cap `AR_BINDER_MAX_ITEMS` (5000). A routine delivery target may set `reviewBeforeSend`.
- **Done when:** `verify_binder.py` accepts a built ZIP and rejects a byte flip; a delivery with `reviewBeforeSend` does not send until the review item is `signed`.
- **Tests:** manifest hash; tamper; item cap; review-before-send Temporal test.

### M14-T13 · Solution-pack extension hooks
- **Depends on:** M3-T09
- **Areas:** `ar_api/plugins.py`, `ar_domain/packs/alembic_env.py`, `ar_domain/packs/registry.py`, import-linter contract `packs-not-in-core`, migration `0029_pack_extension`, `apps/web` nav from `GET /api/v1/tenant/packs`
- **Spec:** [spec 21 §6](../03-specs/21-records-governance.md#6-pack-extension-points), [schema §28](../04-data/schema.md#28-pack-enablement-ar_domainpacks), [migrations §6](../04-data/migrations.md#6-pack-schemas), [ADR-0023](../02-architecture/adr/ADR-0023-pack-extensions.md), [OQ-28](../open-questions.md)
- **Do:** Tables `pack_registrations` (`tenant_id` nullable) and `tenant_pack_flags`. Mount helper at `/api/v1/ext/{pack_id}`. `ar_domain.packs.alembic_env` with version table `{schema}_alembic_version`. `register_pack_permissions` and `register_pack_audit_actions`. Manifest `configSchema` stored on `tenant_pack_flags.settings`, and `ui` slots `nav`, `settings`, `guestPortals`, `admin` ([extension-framework](../05-contracts/extension-framework.md)). Testing kit `ar_testing.packs.install_fixture`. Import-linter forbids `ar_pack_*` from `libs/` and `services/`. Replace the M3-T09 `extension_unavailable` stub so a signed manifest with `extension` runs the pack migration and then imports resources. `dropSchema` requires step-up and returns 409 `hold_active` when a hold covers a pack row. Signature keys are `AR_PACK_TRUSTED_KEYS`. Core does not import a pack package.
- **Done when:** a fixture pack with its own schema installs, enables, disables (data kept) and uninstalls; `dropSchema` without step-up is refused; a core module that imports `ar_pack_grc` fails the linter.
- **Tests:** fixture pack Alembic upgrade; enable flag 404; hold blocks drop; linter contract.
