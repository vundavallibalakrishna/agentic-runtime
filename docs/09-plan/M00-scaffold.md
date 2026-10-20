# M0 — Scaffold & tooling

Goal: an empty but fully wired monorepo. After M0 any later task only adds code; it never has to invent tooling.

Exit criteria: `make bootstrap && make dev` starts the local stack; `make check` (lint, typecheck, unit tests for Python and TS) passes; CI is green on a PR; `make gen` produces `openapi.json`, `@ar/api-client` and `ar_client` without diff.

---

### M0-T01 · Monorepo skeleton
- **Depends on:** —
- **Areas:** `pyproject.toml`, `uv.lock`, `package.json`, `pnpm-workspace.yaml`, `turbo.json`, `biome.json`, `Makefile`, `lefthook.yml`, `.editorconfig`, `.gitignore`, `.python-version`, `.nvmrc`, `libs/*`, `services/*`, `connectors/*`, `apps/web`, `packages/*`, `docs/09-plan/progress.md`
- **Spec:** [service-decomposition §4](../02-architecture/service-decomposition.md#4-repository-layout), [coding-standards-python](../08-quality/coding-standards-python.md), [coding-standards-typescript](../08-quality/coding-standards-typescript.md)
- **Do:** Create the uv workspace with every Python project from service-decomposition §1–2 as a member (`src/` layout, `pyproject.toml` with name, version `0.1.0`, `requires-python = ">=3.14"`, empty `__init__.py`, one trivial unit test). Configure ruff (rules in coding-standards-python §2), mypy strict + pydantic plugin, pytest (`asyncio_mode=auto`, markers `unit`, `integration`, `e2e`, `slow`), import-linter contracts (layering diagram), deptry. Create pnpm workspace (`apps/web`, `packages/*`), turbo pipeline (`build`, `lint`, `typecheck`, `test`, `gen`), biome config. Makefile targets exactly as listed in [local-dev §2](../07-ops/local-dev.md#2-make-targets-the-only-entry-points) (targets whose tooling arrives later print `not available until <task id>` and exit 0). lefthook pre-commit: ruff format/check and biome on staged files. Create `docs/09-plan/progress.md` with a header line.
- **Done when:** `uv sync` and `pnpm install` succeed from a clean clone; `make check` passes; `lint-imports` passes with the layering contracts; an intentional cross-service import in a scratch branch fails `lint-imports`.
- **Tests:** trivial test per Python project; `apps/web` placeholder Vitest test.

### M0-T02 · Verify and pin dependencies
- **Depends on:** M0-T01
- **Areas:** `pyproject.toml` files, `package.json` files, lockfiles, `docs/stack.md`, `renovate.json`
- **Spec:** [stack.md](../stack.md), [open-questions OQ-15](../open-questions.md)
- **Do:** Add every dependency listed in stack.md to the projects that need it (per service responsibilities), resolve lockfiles, and check each pinned version exists in the registry. Where a pin does not resolve, choose the closest released version, update the row in stack.md with the reason, and note it in `progress.md`. Configure Renovate (weekly, grouped: python-minor, js-minor, infra-images; automerge patch for dev tools only).
- **Done when:** `uv lock --check` and `pnpm install --frozen-lockfile` succeed; every row in stack.md matches the lockfile (script `scripts/check_stack_pins.py` compares and fails on mismatch).
- **Tests:** `scripts/check_stack_pins.py` runs in CI.

### M0-T03 · `ar_common` core
- **Depends on:** M0-T01
- **Areas:** `libs/ar_common/src/ar_common/{settings.py,mode.py,logging.py,ids.py,errors.py,jcs.py,time.py,pagination.py}`
- **Spec:** [api-conventions](../05-contracts/api-conventions.md), [deployment-modes](../00-overview/deployment-modes.md), [ADR-0020](../02-architecture/adr/ADR-0020-ids-pagination-errors.md)
- **Do:** `BaseServiceSettings` (pydantic-settings, prefix `AR_`, common fields `AR_ENV`, `AR_DEPLOYMENT_MODE`, `AR_OTEL_EXPORTER_OTLP_ENDPOINT`, `AR_LOG_HASH_USER_IDS`); `mode.is_saas()/is_single_tenant()`; structlog JSON logging with trace ids and secret-field scrubbing; `new_id()` (UUIDv7); `ArError` hierarchy mapped to RFC 9457 problem types and error codes from api-conventions; `canonical_json()` + `args_hash()` (rfc8785, sha256 hex); `utcnow()`; signed opaque pagination cursors (HMAC with `AR_CURSOR_SECRET`).
- **Done when:** all functions documented and typed; error code enum matches api-conventions exactly.
- **Tests:** unit tests; hypothesis property tests for `canonical_json` (key order and number formatting invariance) and cursor round-trip/tamper detection.

### M0-T04 · `ar_common` clients and telemetry
- **Depends on:** M0-T03
- **Areas:** `libs/ar_common/src/ar_common/{telemetry.py,metrics.py,http.py,valkey.py,s3.py,internal_jwt.py,keys.py}`
- **Spec:** [internal-apis §1](../05-contracts/internal-apis.md), [spec 18](../03-specs/18-observability-eval.md), [tenancy-isolation §5](../02-architecture/tenancy-isolation.md#5-mandatory-isolation-tests)
- **Do:** `ar_common.telemetry.setup(service_name)` (OpenTelemetry traces + metrics, OTLP exporter, resource `service.name`, auto-instrumentation), Prometheus registry helper; `http_client()` factory (httpx, timeouts, OTel instrumentation, retries via tenacity for idempotent methods); Valkey client factory; S3 wrapper (aiobotocore + presign via boto3); internal JWT sign/verify (EdDSA, claims per internal-apis, ≤ 60 s, `jti` replay cache in Valkey); `ar_common.keys` Valkey key builders (every key includes tenant or a UUID).
- **Done when:** a JWT signed by service A verifies at B with the shared JWKS and fails with wrong `aud`, expired `exp` or replayed `jti`.
- **Tests:** unit tests for JWT (valid/expired/aud/replay), key builder lint test (`test_keys_include_tenant_or_uuid`).

### M0-T05 · HTTP service template
- **Depends on:** M0-T04
- **Areas:** `libs/ar_common/src/ar_common/web/{app.py,middleware.py,problems.py,health.py}`; `services/{api,model_gateway,mcp_gateway,sandbox_manager,channels}/src/*/main.py`
- **Spec:** [spec 01 §§1–2](../03-specs/01-api-bff.md), [api-conventions](../05-contracts/api-conventions.md)
- **Do:** `create_app(service_name, settings, routers, readiness_checks)` with request-id middleware (`X-Request-Id`), access logging, problem+json exception handlers, body-size limit (`AR_MAX_JSON_BODY_BYTES`), `GET /healthz`, `GET /readyz` (runs checks), `GET /metrics`. Each HTTP deployable gets a `main.py` and settings class; `uvicorn` entry in `pyproject` scripts.
- **Done when:** each service starts locally and answers `/healthz` 200, `/readyz` 200 or 503 with failing check names.
- **Tests:** unit tests for problem mapping, request-id propagation, readiness failure.

### M0-T06 · Local stack (`compose.yaml`)
- **Depends on:** M0-T01
- **Areas:** `compose.yaml`, `deploy/compose/**` (Keycloak realm export `agentic-runtime-realm.json`, Postgres init SQL creating roles `ar_owner`, `ar_app`, `ar_platform`, `ar_readonly`, OPA config, Squid config, OTel collector config, Grafana provisioning), `.env.example`
- **Spec:** [local-dev](../07-ops/local-dev.md), [service-decomposition §6](../02-architecture/service-decomposition.md#6-ports-local-development)
- **Do:** Compose services with the ports in service-decomposition §6: Postgres+pgvector, Valkey, Temporal (`temporal server start-dev` with Postgres-less SQLite persistence for dev), Keycloak (realm import with clients `ar-web`, `ar-api`, `ar-admin`, `ar-token-exchange`, organization `dev`, users `admin@dev.local`, `builder@dev.local`, `member@dev.local`, `approver@dev.local`), SeaweedFS (S3), OpenBao dev mode, OPA, Mailpit, Squid, ClamAV (profile `scan`), Qdrant (optional profile `qdrant`, only for the optional retrieval adapter), observability stack (profile `obs`: OTel collector, Prometheus, Tempo, Loki, Grafana, Langfuse). App services run on the host via `make dev` (honcho/Procfile.dev) by default or in Compose with profile `apps`.
- **Done when:** `make dev` brings everything up healthy within 3 minutes on a laptop; `make down` cleans up; `.env.example` documents every variable used locally.
- **Tests:** CI job `compose-smoke` starts the stack and curls each health endpoint.

### M0-T07 · `fake-llm` service
- **Depends on:** M0-T05
- **Areas:** `services/fake_llm/**`, `libs/ar_testing/src/ar_testing/fake_llm.py`
- **Spec:** [testing-strategy §4](../08-quality/testing-strategy.md#4-fake-llm), [spec 04](../03-specs/04-model-gateway.md)
- **Do:** OpenAI-compatible `/v1/chat/completions` (streaming and non-streaming, tool calls, usage), `/v1/embeddings` (deterministic: sha256-seeded unit vectors, any dimension), `/v1/rerank` (lexical overlap score), `/v1/tokenize`, `/v1/models`. Behaviour driven by scripts: `POST /_scripts` registers a script `{match: {contains|regex|last_tool_result}, respond: {text|tool_calls|error|delay_ms}}`; default reply echoes `fake: <last user text>`. Scripts scoped by header `X-Fake-Script-Set` so parallel tests do not collide.
- **Done when:** the openai Python client streams from it; tool-call scripts produce valid tool_call deltas.
- **Tests:** unit tests for each endpoint and script matching.

### M0-T08 · Web app skeleton
- **Depends on:** M0-T01
- **Areas:** `apps/web/**`, `packages/tsconfig/**`
- **Spec:** [spec 19](../03-specs/19-web-app.md), [coding-standards-typescript](../08-quality/coding-standards-typescript.md)
- **Do:** Next.js App Router project, Tailwind 4, shadcn init (base components: button, input, dialog, dropdown-menu, table, tabs, toast via sonner, form, badge, card, sheet, tooltip, skeleton), TanStack Query provider, next-intl (en), theme (light/dark), layout shell with sidebar placeholder, `/healthz` route handler, error and not-found pages; Vitest + Testing Library + MSW; Playwright config (base URL `http://localhost:3000`); Storybook; knip.
- **Done when:** `pnpm --filter @ar/web build` succeeds; `pnpm test` and a Playwright smoke test (home renders) pass.
- **Tests:** component test for the shell; Playwright smoke.

### M0-T09 · Codegen pipeline
- **Depends on:** M0-T05, M0-T08
- **Areas:** `scripts/gen_openapi.py`, `scripts/gen_json_schema.py`, `packages/api-client/**`, `libs/ar_client/**`, `libs/ar_contracts/src/ar_contracts/__init__.py`, Makefile `gen`
- **Spec:** [ADR-0017](../02-architecture/adr/ADR-0017-openapi-first-codegen.md), [api-conventions](../05-contracts/api-conventions.md)
- **Do:** `make gen` = export `openapi.json` from `ar_api` app (no server needed) → `@hey-api/openapi-ts` to `packages/api-client/src/gen` (client + TanStack Query plugin) → `openapi-python-client` to `libs/ar_client`; export JSON Schema of `ar_contracts` stream events and definitions to `packages/api-client/src/schemas/*.json` and generate TS types. Commit generated code.
- **Done when:** CI job `codegen-drift` runs `make gen` and fails on any diff.
- **Tests:** CI job; a Vitest test imports the generated client.

### M0-T10 · CI pipelines
- **Depends on:** M0-T02, M0-T06, M0-T09
- **Areas:** `.github/workflows/{ci.yml,images.yml,nightly.yml}`
- **Spec:** [ci-cd](../07-ops/ci-cd.md)
- **Do:** Jobs per ci-cd.md §2: `python-lint` (ruff, mypy, lint-imports, deptry), `python-unit`, `python-integration` (testcontainers), `web` (biome, tsc, vitest, knip, build), `codegen-drift`, `opa-test`, `migrations` (placeholder until M1), `compose-smoke`, `images` (build only on PR), with caching (uv, pnpm, turbo). Required checks documented.
- **Done when:** a PR runs all jobs green in < 15 minutes.
- **Tests:** the pipeline itself.

### M0-T11 · Container images
- **Depends on:** M0-T05, M0-T08
- **Areas:** `images/python-service.Dockerfile`, `images/web.Dockerfile`, `images/sandbox/Dockerfile` (placeholder), `images/squid/`, `images/ingest/` (placeholder), `.dockerignore`
- **Spec:** [ci-cd §3](../07-ops/ci-cd.md#3-images), [helm-k8s](../07-ops/helm-k8s.md)
- **Do:** Multi-stage uv build parameterised by `SERVICE` (one Dockerfile builds `api`, `runtime`, `system`, `ingest`, `model_gateway`, `mcp_gateway`, `sandbox_manager`, `channels`, `mcp_sql`, `mcp_openapi`, `fake_llm`, plus `migrate` = `ar_domain` with the Alembic entrypoint; image names per ci-cd §3), non-root UID 10001, read-only root FS compatible, `tini` entrypoint; web image with Next standalone output. SBOM (syft) and cosign signing in `images.yml` on main.
- **Done when:** all images build; each container passes `/healthz` in compose `apps` profile; images < 400 MB (ingest and sandbox excepted).
- **Tests:** CI image build + container smoke.

### M0-T12 · `ar_testing` fixtures
- **Depends on:** M0-T04, M0-T07
- **Areas:** `libs/ar_testing/src/ar_testing/{containers.py,temporal.py,fake_llm.py,auth.py,factories/__init__.py}`, `conftest.py` templates
- **Spec:** [testing-strategy](../08-quality/testing-strategy.md)
- **Do:** session-scoped testcontainers (Postgres+pgvector image from stack.md, Valkey, SeaweedFS optional; Qdrant only for the `retrieval_store` fixture's `qdrant` param, skipped unless pytest runs with `--with-qdrant`, as CI job `conformance-qdrant` does), Temporal `WorkflowEnvironment` fixture (time-skipping), in-process fake-llm fixture, helpers to mint internal JWTs and fake sessions. Factories module (polyfactory) populated by later tasks.
- **Done when:** a sample integration test uses Postgres + Valkey containers and passes in CI.
- **Tests:** sample integration test.
