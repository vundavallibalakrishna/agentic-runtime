# M14 — Security hardening & compliance

Goal: production-grade safety and compliance. Input/output guardrails, prompt-injection defences, PII redaction, retention, DPDP data-principal rights (access, correction, erasure, grievance), audit export and SIEM streaming, support-access controls, security testing and fixes.

Exit criteria: the threat-model verification table ([threat-model §4](../06-security/threat-model.md#4-verification)) is all green; red-team suite pass rate ≥ the gate; erasure of a user removes all personal content within 24 h and is evidenced in audit; ZAP baseline and dependency scans have no high findings.

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
