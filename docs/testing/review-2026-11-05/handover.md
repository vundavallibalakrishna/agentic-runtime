# Handover — branch `hardening/m32-remediation` (5 Nov 2026)

This branch applies the first phases of [the review and remediation plan](review-and-remediation-plan.md).
It was built in a git worktree from `origin/main` at `80ba211` (PR 44, the document-analysis redaction fix),
because the main checkout was being driven by other agents at the same time. Nothing is pushed or merged.

## What landed (one commit per task, oldest first)

| Commit | Task | Change |
|---|---|---|
| `938ab73` | M32-T00 | Review report, fresh-pass and GRC-flow evidence committed; `.secrets/` and `apps/web/.next-*/` ignored |
| `574df81` | M32-T02 | Every settings read goes through `settings_for(store, tenant_id)`: no first-tenant fallback in guardrails, the web-fetch feature check or the evidence TSA check. `privacy.redactionSkipEntities` added. Pre-commit ruff honours `extend-exclude`. |
| `267de52` | M32-T03, T04 | A `requester`-mode approval whose requester is SoD-blocked can be decided by any `approvals:decide` holder (fresh-seed deadlock). Outside dev/ci a fake alias fails the run with `model_unavailable`; the gateway returns 502 instead of echoing `fake:`. |
| `43f9ab6` | M32-T05, T06 | Scripted compositions and keyword tool triggers run only where fake models are allowed. The builder drafts with the tenant `reasoning` model, repairs once from validation errors, and falls back to the deterministic proposal last. |
| `a117365` | M32-T07 | Cost per model call from `price_*_micros_per_mtok`; input/output usage events per call with run and model ids; `usage_events` flushed to Postgres and reloaded on bind; prices on `POST /api/v1/models` and the Models screen (Advanced); token in/out swap fixed; checkpoint carries token counts. |
| `1c1e774` | M32-T08, T10 | `models.request_options` (revision 0032) replaces six Qwen3 name checks; `requestOptions` on the models API; Helm sets `AR_APP_MODULE`/`AR_PORT` per HTTP workload and runs workers through their console scripts. |
| `aab95f3` | M32-T09 | `features.assurance` (default off) gates the assurance routes (404), strips the `records` permissions from sessions and hides the nav item; dev seed turns it on; session reports tenant features, locale and timezone; neutral builder starter prompt. |
| `80f4a04` | M32-T02 | M4 edge test passes the calling tenant to web fetch. |
| `c775a9b` | M32-T07 | `refresh_models` kept prices and request options (it rebuilt rows before every turn and zeroed cost); budget and provider-error stops record the usage spent. |

Open-question decisions: OQ-78 to OQ-85 in [open-questions](../../open-questions.md). Milestone file:
[M32-hardening.md](../../09-plan/M32-hardening.md); progress rows in [progress.md](../../09-plan/progress.md).

## What was verified

- Python: full suite `uv run pytest -m "not e2e" --cov` on the final commit: **720 passed, 4 failed, 86 %
  branch coverage** (gate 85 %). The four failures also fail on `main` on this laptop: two Qdrant
  conformance tests (no `qdrant_client` installed), the OPA fixture test (no `opa` binary), and
  `test_w3_requires_step_up_and_reviews_sign_off`, where the W3 delete is denied instead of held. On this
  laptop `pydantic-settings` reads the local `.env` during tests, so `AR_OPA_URL` points at the shared OPA
  container on 8181, which serves a bundle pushed by another running API; pointing it at an unreachable
  port makes a second policy test fail too. The test passed on the branch before the merge from `main` and
  fails on `main` itself here, so it is environment coupling rather than this branch. Worth isolating the
  unit tests from `.env` and from a live OPA. The baseline on `main` was 684 passed; the branch adds 36 tests.
- After merging `origin/main` (M33a seeded SoD policy, M34a office create, M33c eval gym): the three
  documentation conflicts were resolved by keeping both sides, my open-question ids moved to OQ-78 to
  OQ-85 because upstream had taken OQ-70 to OQ-72, and upstream's `test_requester_mode_deadlocks…` was
  rewritten to the new behaviour (another approver may decide; the owner still gets 422).
- `uv run mypy` clean (605 files), `lint-imports` 6 contracts kept, `ruff check` clean, biome clean,
  `scripts/check_public_camel_case.py` 190 models camelCase, web `tsc` clean, web unit tests 44 passed.
- Migration 0032 upgraded, downgraded and re-upgraded on a fresh database; `alembic check` reports no drift.
- `make gen` regenerated `openapi.json`, the TS types and the Python client for the new model fields.
- Live, on the review stack with `Qwen/Qwen3-32B` and `BAAI/bge-m3` through DeepInfra:
  - provider `:test` → `pong` (1.1–1.5 s);
  - a chat turn drove five tool calls (`general.code` twice failed on the model's own code, then succeeded,
    `general.write_file`, `general.read_file` → `323`);
  - a second turn recorded **237 micros** of cost from the model's prices, and after an API restart the
    usage summary reloaded the persisted events (22,152 tokens);
  - the builder drafted "Vendor Security Questionnaire Helper" with a `knowledge` tool from a one-sentence
    description, no validation errors;
  - the Models screen shows the price fields in Advanced mode; `/admin/assurance` is in the nav for the dev
    tenant (flag on) and the assurance routes answer 404 for a tenant with the flag off (API test).
- Screenshot matrix (desktop 1440×900 light and dark, flows, walkthrough video) from the project's own
  certification UI script: `docs/testing/review-2026-11-05/screens/` (71 files).

## Defects seen live on this branch (not fixed here)

1. **Chat SSE drops after ~15 s of silence.** During the five-tool-call turn the chat pane showed an empty
   assistant message with no tool progress while the run was still working; the trace page had it all.
   Matches the review's SSE finding (`iter_events` 15 s timeout, no keep-alive). Phase 2.4.
2. **Default token budget is too small for multi-step tool use.** The assistant's `max_tokens` 16,000
   counts the whole context on every step, so a six-step turn stops with `budget_exceeded` after ~3k-token
   steps. Raise the default or count only new tokens per step.
3. **Redaction masks UUID segments in tool errors fed back to the model** (`01a1ab39-[US_DRIVER_LICENSE]-…`
   inside a workspace path), which can stop the model reusing a path. Extend the analysis profile or exempt
   run-workspace paths (OQ-66).
4. **Duplicate platform rows after a durable bind**: the Models screen lists `fake-llm` and `reasoning`
   twice (in-memory demo seed plus the hydrated DB rows). Cosmetic, but it confuses alias resolution reviews.
5. **`requestOptions` is camelCased on the way out** by the public-JSON middleware
   (`chatTemplateKwargs`), so a client that reads and re-posts a model would corrupt the provider keys.
   The stored value is correct. Exempt free-form JSON fields from key conversion.
6. **`next build` with `AR_NEXT_DIST` rewrites `apps/web/next-env.d.ts`** to the alternate directory; it
   must be reverted before committing (done on this branch).

## CI fixes after the merge

The first CI run on PR 49 failed three checks. `codegen-drift`: the merge brought new endpoints, so
`make gen` was re-run and the generated OpenAPI document and clients committed. `web`: knip flagged the
GRC-flow helper script as an unused file; `docs/testing/**/*.cjs` is now ignored. `web-e2e`: the assurance
spec saw `feature_disabled` because the in-memory identity store built the dev tenant from bare
`TenantSettings()` defaults, so the first tenant-settings patch from any screen replaced the chat store's
row and switched `features.assurance` off. All three places that create the dev tenant now share
`dev_tenant_settings()`, `make seed` turns the flag on for a dev tenant seeded before the flag existed, and a
regression test patches settings and checks the desk stays reachable. Locally the same spec also fails when
`.env` points the e2e API at a database whose dev tenant predates the flag; run `make seed` once.

## What remains (from the plan)

- **Phase 1 leftovers:** async and parallel tool execution (tool calls still block the event loop); token
  streaming end to end; real embeddings for memory and tool search; LLM memory extraction and compaction;
  gateway fallback routing, breaker, provider-side JSON schema, native Anthropic adapter; evals that run the
  real agent with an LLM judge; model-driven skill loading; sandbox isolation in prod and a real browser;
  MCP session reuse, pagination, resources; demo tool fixtures (tickets, petstore, warehouse) still seed in
  every environment (OQ-81).
- **Phase 2 (the big one):** retire the process-local write-behind `ChatService` in favour of the
  repository/unit-of-work layer; hydrate per tenant (today only `slug='dev'`); Valkey-backed sessions,
  idempotency, rate limits and SSE fan-out; Temporal activity per step with `continue_as_new`; worker
  concurrency settings wired; a kind install that serves a chat turn; a real load test; nightly scanners
  and soak that actually run.
- **Phase 3:** `run_steps` written per model call; gateway metrics; delete the spec-scraping placeholder
  metrics; fix the overview maths; analytics screens for cost by model/agent/user over time, latency
  percentiles, most-used tools and skills.
- **Phase 4 leftovers:** neutral platform defaults for timezone, locale and currency (today `Asia/Kolkata`,
  `en-IN`, `INR` with the dev tenant inheriting them); pack-provided UI (`/ext/*`); tenant settings screen;
  connector catalogue as data; admin UI for roles, groups, teams, keys, webhooks and audit.

## How to run the review stack again

The compose dependencies are the project's usual ones (`make up`); this pass used the compose Postgres on
**5433**. Ports 18131/18132 belong to another session's stack on this laptop, so the review used its own.

```bash
# from the worktree: /Users/balakrishnavundavalli/working/talentfino/cura/agentic_runtime/.claude/worktrees/m32
cp ../../../.env .env   # dev keys; gitignored
docker exec agentic-runtime-postgres-1 psql -U ar_owner -d postgres -c "CREATE DATABASE m32_review OWNER ar_owner;"
AR_DATABASE_URL='postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:5433/m32_review' uv run alembic -c libs/ar_domain/alembic.ini upgrade head
AR_DATABASE_URL='postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:5433/m32_review' uv run python scripts/seed.py
AR_DATABASE_URL='postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:5433/m32_review' AR_MG_PORT=18201 uv run ar-model-gateway
AR_DATABASE_URL='postgresql+asyncpg://ar_app:ar_app@127.0.0.1:5433/m32_review' AR_PORT=18231 AR_TEMPORAL_ADDRESS=127.0.0.1:1 AR_OPA_URL= AR_MODEL_GATEWAY_URL=http://127.0.0.1:18201 AR_PUBLIC_URL=http://127.0.0.1:18232 AR_WEB_HOST_PORT=18232 uv run ar-api
# from apps/web
API_PROXY_URL=http://127.0.0.1:18231 AR_NEXT_DIST=.next-m32 pnpm exec next build
API_PROXY_URL=http://127.0.0.1:18231 AR_NEXT_DIST=.next-m32 pnpm exec next start --port 18232
```

Then open http://127.0.0.1:18232, sign in as `admin@dev.local`, and register the provider in Models →
Advanced → OpenAI-compatible with the key from `.secrets/deepinfra_api_key` (never commit or paste it).
Set the input and output prices to see cost on the Usage screen. The screenshot sweep is the project's
`scripts/m31_ui.cjs`; run it from `apps/web` with `NODE_PATH=$PWD/node_modules` after replacing its
hard-coded `/workspace/...` Playwright require with `require("@playwright/test")`.

## Suggested next steps

1. Open a pull request from `hardening/m32-remediation` (nine conventional commits, each one task) and let
   the hosted CI run `helm lint`, `opa test` and the migrations job, which this laptop could not.
2. Decide the four owner questions in the plan (assurance as flag or pack, Phase 2 approach, second
   provider, fate of `mcp-gateway`).
3. Start Phase 2 with the SSE keep-alive and the per-tenant hydration, which hurt most in the live pass.
