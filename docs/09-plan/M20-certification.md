# M20 — Platform certification

Goal: certify the product the way an operator and a tester would, on a fresh stack, with a real OpenAI-compatible model. No mock model, no scripted screen filler.

Exit criteria: `docs/testing/m20-certification-report.md` records a scenario pass/fail table from a run that actually happened, with screenshots and a walkthrough. The verdict is certified, certified with conditions, or not certified. A defect that is small is fixed in this milestone with a regression test. A defect that is large is an open question with a severity.

Model: DeepInfra's OpenAI-compatible API (`https://api.deepinfra.com/v1/openai`), chat model `Qwen/Qwen3-32B`. The operator pastes the key into **Admin → Models** (Advanced). The key is stored through the secret store and is never returned by the API.

**Depends on:** M0–M19 exit.

**Spec:** [principles](../00-overview/principles.md), [spec 04](../03-specs/04-model-gateway.md), [local-dev](../07-ops/local-dev.md), [ux-quality](../08-quality/ux-quality.md), [design-system](../08-quality/design-system.md), [OQ-48](../open-questions.md) through [OQ-53](../open-questions.md).

## M20-T01 — Registered provider routing

**Do:** `POST /api/v1/model-providers` accepts `apiKey` and stores it as a `db_encrypted` secret. The public row returns `hasApiKey` and never the key. Creating a model and a tenant `reasoning` alias is written to Postgres so the API and the runtime worker see the same catalogue. `model-gateway` `POST /v1/chat/completions` calls that provider when the body names its upstream model. `fake-chat` stays on fake-llm. A named model with no row returns 502 rather than a fake echo.

**Done when:** a unit test posts a completion for `Qwen/Qwen3-32B` and the gateway calls the registered base URL with the key only in the `Authorization` header. The response body does not contain the key. Chat on a tenant `reasoning` alias sends that upstream model and strips a `<think>` trace.

**Tests:** `libs/ar_domain/tests/unit/test_m20_provider.py`, `services/model_gateway/tests/unit/test_upstream.py`.

## M20-T02 — Operator model screen

**Do:** **Admin → Models** Advanced mode lets an operator choose OpenAI-compatible, set the base URL, the upstream model and a write-only API key, then register and test. Simple mode still registers the local fake provider. The key field is cleared after submit.

**Done when:** the models screen test submits `apiKey` and the rendered page does not show the secret.

**Tests:** `apps/web/src/components/models/models-admin.test.tsx`.

## M20-T03 — Full-stack certification run

**Do:** Bring the stack up from the documented run guide on free host ports (do not stop or retarget any other compose project). Sign in through the UI. Configure DeepInfra from Models. Drive chat, agents, tools and approvals, knowledge, evals, policies, dashboards, admin, settings, and the GRC pack (frameworks, controls, evidence, connectors, control tests, findings, questionnaires, vendors, policies, risks, incidents, audit desk, access reviews, reports) in the browser. Enter data through the UI. Empty states stay empty until a person would have filled them. Capture light and dark, desktop and mobile.

**Done when:** every scenario in the report was actually run, and each small defect found on that pass has a fix and a regression test.

**Tests:** the M20-T01 and M20-T02 tests, plus the local Playwright pass recorded in the report. The Playwright file stays skipped unless `AR_M20_CERT=1`, so CI does not call the external model.

## M20-T04 — Report, checklist and walkthrough

**Do:** `docs/testing/m20-checklist.md`, screenshots under `docs/testing/m20/`, a walkthrough of the main flows, and `docs/testing/m20-certification-report.md`. Separate platform defects from Qwen3-32B limitations. Record deferred gaps: GRC HTTP rows on the process store (OQ-49 to OQ-52), the 24 h soak, and live Slack, Teams and a customer IdP (OQ-48). Circuit-breaker, semaphore and streaming fallback from spec 04 stay off the request path (OQ-53).

**Done when:** the report states one verdict and does not claim a scenario that was not run.

## How to test visually

1. `make bootstrap` then set free host ports in `.env` (or `make dev AUTO_PORTS=1` when the defaults are taken). `make up && make migrate && uv run alembic -c packs/grc/alembic.ini upgrade head && make seed`, then `uv run honcho start -f Procfile.dev`.
2. Sign in as `admin@dev.local` (password `dev-password` on the Keycloak form, or the dev sign-in button).
3. Open **Admin → Models**, switch to Advanced, register an OpenAI-compatible provider at `https://api.deepinfra.com/v1/openai` with upstream model `Qwen/Qwen3-32B`, and point chat at it. The sample line should be the model's words, not a `fake:` echo.
4. Walk the checklist in [m20-checklist](../testing/m20-checklist.md).
