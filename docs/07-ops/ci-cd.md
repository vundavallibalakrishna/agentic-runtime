# CI/CD

CI runs on the repository's hosted CI (workflow files in `.github/workflows/`; any runner that executes the same Make targets is acceptable). Every job calls a Make target or script so the pipeline is portable.

## 1. Branching and merge rules

- Trunk-based: short-lived branches → pull request → squash merge to `main`. Conventional Commits in PR titles (`feat(runtime): …`), checked by CI.
- Required checks: all jobs in §2 marked **required**; one approving review; CODEOWNERS for `policies/`, `libs/ar_domain/src/ar_domain/migrations/`, `deploy/helm/`, `docs/06-security/`.
- `main` is always releasable; feature flags (`tenants.settings.features.*`, plan features) hide incomplete features.

## 2. Jobs

| Job | Trigger | Required | Runs | Budget |
|---|---|---|---|---|
| `pr-title` | PR | yes | Conventional-commit lint | 10 s |
| `python-lint` | PR, main | yes | `ruff format --check`, `ruff check`, `mypy --strict`, `lint-imports`, `deptry` | 4 min |
| `python-unit` | PR, main | yes | `pytest -m "not integration" -n auto --cov` per project; coverage gate ([testing-strategy §8](../08-quality/testing-strategy.md#8-coverage-and-gates)) | 5 min |
| `python-integration` | PR, main | yes | `pytest -m integration` with testcontainers (Postgres+pgvector, Valkey, SeaweedFS, OPA, Keycloak where needed), including the `RetrievalStore` conformance suite for the pgvector adapter and Temporal test server; sharded ×4 | 10 min |
| `web` | PR, main | yes | `biome check`, `tsc --noEmit`, `vitest run --coverage`, `knip`, `next build` | 6 min |
| `codegen-drift` | PR, main | yes | `make gen` then `git diff --exit-code` | 3 min |
| `opa-test` | PR, main | yes | `opa fmt --diff`, `opa check --strict`, `opa test policies/ --coverage` (≥ 90 %) | 1 min |
| `migrations` | PR, main | yes | `alembic upgrade head` on empty DB → `alembic check` (no autogenerate diff) → downgrade one → upgrade; RLS coverage test (every tenant table has RLS + policy, [rls](../04-data/rls.md)); squawk lint for locking migrations | 3 min |
| `compose-smoke` | PR, main | yes | `docker compose --profile deps --profile apps up -d`, wait for `/healthz` on every service, run `scripts/smoke.py` (login with seeded user via password grant, create conversation, run against fake-llm, receive `run.completed`) | 8 min |
| `conformance-qdrant` | PR touching `libs/ar_domain/src/ar_domain/knowledge/store*`, nightly | yes when triggered | `RetrievalStore` conformance suite with the `qdrant` param (Qdrant testcontainer) plus the pgvector → qdrant → pgvector migration round trip ([spec 10 §10](../03-specs/10-knowledge.md#10-retrievalstore-conformance-suite)) | 10 min |
| `e2e` | PR (label `e2e`), main, nightly | main: yes | Playwright + axe against compose stack ([testing-strategy §6](../08-quality/testing-strategy.md#6-end-to-end-tests)) | 15 min |
| `security` | PR, main | yes | §5 scanners | 4 min |
| `images` | PR (build only), main (build+push+sign) | yes | §3 | 10 min |
| `helm` | PR touching `deploy/`, main | yes | `helm lint`, `helm template` for each preset, kubeconform, kind install with `values-dev.yaml` + smoke (main only) | 12 min |
| `eval-gate` | PR touching `ar_runtime/prompts/**`, `ar_runtime/context/**`, model aliases; nightly | yes when triggered | `make eval` golden + red-team suites against staging models; thresholds in [eval-strategy §5](../08-quality/eval-strategy.md#5-gates) | 20 min |
| `nightly` | cron 02:00 IST | — | Full e2e, isolation suite, fuzz (`schemathesis` against openapi.json), dependency audit, 30-min soak with Locust on kind | 90 min |
| `docs` | PR touching `docs/` | yes | Link/anchor check, Mermaid render check (`mmdc`), `scripts/check_env_catalogue.py`, `scripts/check_audit_catalogue.py` | 2 min |

PR wall-clock target: < 15 minutes (jobs run in parallel). Caches: uv cache keyed by `uv.lock`, pnpm store by `pnpm-lock.yaml`, turbo remote cache (self-hosted), Docker layer cache via registry.

## 3. Images

| Image | Dockerfile | Contents |
|---|---|---|
| `ar-api`, `ar-runtime`, `ar-system`, `ar-model-gateway`, `ar-mcp-gateway`, `ar-sandbox-manager`, `ar-channels`, `ar-mcp-sql`, `ar-mcp-openapi`, `ar-fake-llm`, `ar-migrate` | `images/python-service.Dockerfile` (`--build-arg SERVICE=…`) | Python 3.14 slim base, uv-installed wheel set from `uv.lock` (`uv sync --frozen --no-dev --package <svc>`), non-root UID 10001, `tini`, read-only root FS, no shell utilities beyond base |
| `ar-ingest` | `images/ingest/Dockerfile` | Python service + LibreOffice headless, Tesseract/OCR models, Docling models baked in |
| `ar-web` | `images/web.Dockerfile` | Node 24 slim, Next standalone output, UID 10001 |
| `ar-sandbox` | `images/sandbox/Dockerfile` | Debian 13 slim with Python 3.14, Node 24, data libraries, Chromium + Playwright, LibreOffice and `sandbox-agent` ([spec 12 §7.1](../03-specs/12-sandbox-manager.md#71-image-ar-sandbox-imagessandboxdockerfile)) |
| `ar-squid` | `images/squid/` | Squid + `ar-egress-helper` (per-sandbox allowlist lookup) |
| `ar-opa` | upstream OPA image | Pinned by digest; bundle fetched from `api` |

Rules: tags `X.Y.Z` and `sha-<git sha>`; deploys reference **digests**; SBOM (SPDX JSON via syft) attached as OCI artifact; images signed with cosign (keyless in SaaS CI, key-based for customer bundles) and verified at admission (Kyverno/OPA Gatekeeper policy shipped in the chart, optional); base images refreshed weekly by the dependency bot.

## 4. Environments and deployment

- `main` merge → images pushed → **staging** auto-deploy via Helm (`helm upgrade --atomic --wait`) → post-deploy smoke + eval gate.
- **prod (SaaS)**: manual promotion of a tagged release; canary for stateless deployables (10 % → 50 % → 100 %, 15 min each, auto-rollback on SLO burn alert or error-rate > 2× baseline).
- **Single-tenant/on-prem**: customers install tagged releases with the Helm chart; release notes include migration notes and required values changes.
- Database migrations run as a Helm pre-upgrade Job (`ar-migrate`: `alembic upgrade head`) before new pods roll; migrations are expand/contract ([migrations](../04-data/migrations.md)).

## 5. Security scanning

| Scanner | Target | Gate |
|---|---|---|
| gitleaks | Repo diff + full history nightly | Any finding fails |
| osv-scanner / `pip-audit` + `pnpm audit` | `uv.lock`, `pnpm-lock.yaml` | High/critical with fix available fails; others reported |
| Trivy | Built images + Helm chart (misconfig) | Critical fails; high fails after 7-day grace |
| Semgrep (OSS rules) + ruff `S` rules | Python/TS source | Custom rules: no raw SQL string formatting, no `httpx` without `ssrf_guard` in tool code, no `verify=False` |
| zizmor | CI workflow files | Any high finding fails |
| schemathesis (nightly) | Running API | 5xx or schema violation fails nightly |
| ZAP baseline (nightly) | Web app on kind | High fails |

Dependency updates: bot PRs weekly (grouped), security updates immediately; lockfiles always committed.

## 6. Releases and upgrades

- SemVer for the product (chart `version` = app `appVersion`). Minor releases monthly; patch releases as needed. Support policy: current and previous minor.
- Release process (`scripts/release.py`): changelog from Conventional Commits, tag, build/sign images, package chart (OCI), generate air-gap bundle (`make images-bundle`: images + chart + SBOMs + checksums), publish release notes with upgrade notes.
- Upgrade guarantees: N-1 → N upgrade supported without downtime for stateless services; mixed-version window allowed because API/internal contracts are backward compatible for one minor; Temporal workflow changes use `workflow.patched()` or new workflow type versions ([ADR on Temporal](../02-architecture/adr/README.md)); database follows expand/contract across two releases.
- Rollback: `helm rollback` of app pods is always safe within a minor; database migrations are never rolled back in prod (contract steps ship one release later).
