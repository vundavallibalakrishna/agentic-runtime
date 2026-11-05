# M32 — Hardening after the Nov 2026 review

Goal: act on [the end-to-end review](../testing/review-2026-11-05/review-and-remediation-plan.md). Each task is one
pull request unless stated. Tasks are ordered by the review's priority; later phases (store retirement, per-step
Temporal, metrics catalogue) are split into their own tasks when they start.

Depends on: M31.

### M32-T00 · Review record
- **Do:** commit the review, the fresh-pass and GRC-flow evidence; ignore alternate Next.js build dirs and `.secrets/`.
- **Done when:** `docs/testing/review-2026-11-05/` exists and `git status` is clean after a certification pass.

### M32-T01 · Document analysis keeps evidence (landed as PR 44)
- **Done when:** `features.documentAnalysisRedaction` defaults off; check judges paraphrases; a bad settings patch is 422.

### M32-T02 · Tenant-scoped settings reads
- **Spec:** [02-identity-tenancy §3.1](../03-specs/02-identity-tenancy.md), [data-protection §3](../06-security/data-protection.md), [OQ-70](../open-questions.md).
- **Do:** `ar_domain.identity.tenant_settings.settings_for`; guardrails, web-fetch feature and evidence TSA read the
  calling tenant only, with no fallback to another row; `privacy.redaction_skip_entities`; pre-commit ruff honours
  `extend-exclude`.
- **Tests:** `libs/ar_domain/tests/unit/test_m32_tenant_settings.py` (two tenants, opposite toggles; skip list;
  web-fetch per tenant; TSA per actor tenant).
- **Done when:** a tenant disabling redaction does not affect another; a caller without a tenant gets the defaults.

### M32-T03 · Fresh-seed approval policy
- **Do:** the seeded W2 policy resolves on a fresh tenant without a second policy; SoD still excludes the requester.
- **Tests:** fresh seed → W2 POST → owner 422 `sod_violation` → `approver@dev.local` 200.

### M32-T04 · No fake echo for registered models
- **Do:** the model gateway returns 502 `no_healthy_upstream` instead of `fake: {text}` when a non-fake model has no
  upstream; log when an alias resolves to the fake provider outside dev/ci.

### M32-T05 · Remove scripted turn paths
- **Do:** delete `maybe_compose`, `maybe_tools`, keyword tool triggers and demo tool fixtures from the production turn;
  keep them in `ar_testing` for unit tests only.

### M32-T06 · LLM-backed builder
- **Do:** `builder_responder` calls the tenant `reasoning` alias with the Builder instructions and a JSON schema;
  `scripted_definition` is the last repair only.

### M32-T07 · Real cost and persisted usage
- **Do:** compute `cost_micros` from `models.price_*_micros_per_mtok`; write one usage event per model call, tool call
  and sandbox exec; flush `usage_events` to Postgres; fix the tokens in/out swap.

### M32-T08 · Per-model configuration
- **Do:** `enable_thinking`, `max_tokens` and timeouts come from the model row, not substring matches on the name.

### M32-T09 · Assurance feature flag and neutral defaults
- **Do:** `features.assurance` default off hides evidence/holds/binders/AI register/run records; platform defaults for
  timezone, locale and currency are neutral with the India values in the dev seed.

### M32-T10 · Chart starts every deployable
- **Do:** Helm sets `AR_APP_MODULE` per deployable and runs worker `main()` so Temporal pollers start.
