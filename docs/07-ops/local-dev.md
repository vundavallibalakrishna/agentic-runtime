# Local development

Goal: a fresh clone runs the whole product on a laptop in under 15 minutes with `make bootstrap && make dev`, using `fake-llm` so no model access is needed.

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker Engine + Compose v2 | Engine 28+ / Compose 2.40+ | 8 CPU / 16 GB RAM recommended for the full stack |
| uv | 0.13.x | Installs Python 3.14 itself (`.python-version`) |
| Node.js | 24 LTS (`.nvmrc`) | Via fnm/nvm |
| pnpm | 12.x | `corepack enable` |
| make, git, lefthook | any recent | `lefthook install` is run by `make bootstrap` |
| Optional: kind + Helm 3 + kubectl | see [stack](../stack.md) | Only for `make kind-up` (Helm/e2e and Kubernetes sandbox driver) |

Exact versions: [stack.md](../stack.md).

## 2. Make targets (the only entry points)

| Target | Does |
|---|---|
| `make bootstrap` | `uv sync --all-packages`, `pnpm install`, `lefthook install`, copies `.env.example` → `.env` if missing, generates dev keys into `.env` (`AR_SESSION_ENCRYPTION_KEY`, `AR_CURSOR_SECRET`, `AR_DB_ENCRYPTION_KEYS`, `AR_TOKEN_CACHE_KEY`, internal JWT key pair) with `scripts/dev_keys.py` |
| `make up` / `make down` | Start/stop dependency containers from `compose.yaml` (profile `deps`; add `OBS=1`, `SCAN=1`, `QDRANT=1` for the optional `obs`, `scan`, `qdrant` profiles) |
| `make migrate` | `uv run alembic -c libs/ar_domain/alembic.ini upgrade head` and seeds Keycloak realm (import is automatic on first start) |
| `make seed` | `uv run python scripts/seed.py`: tenant `dev` (plan `enterprise`, matching the Keycloak organization `dev`), users `admin@dev.local` (tenant_admin), `builder@dev.local` (builder, tool_owner, knowledge_manager), `member@dev.local` (member), `approver@dev.local` (approver), all with password `dev-password` (defined in the realm export); model provider `fake-llm` with aliases `reasoning`, `fast`, `vision`, `embed`, `rerank`; agent `Helpdesk` with sample knowledge collection and the `mcp-openapi` petstore tool server |
| `make dev` | `make up migrate seed` (idempotent) then runs all app processes with reload via `honcho` (`Procfile.dev`): api, runtime-worker, system-worker, ingest-worker, model-gateway, mcp-gateway, sandbox-manager (Docker driver), channels, mcp-sql, mcp-openapi, fake-llm, web (`pnpm --filter @ar/web dev`) |
| `make dev-min` | Only api, runtime-worker, system-worker, model-gateway, mcp-gateway, fake-llm, web (enough for chat + tools) |
| `make fmt` | `ruff format`, `ruff check --fix`, `biome check --write` |
| `make test-integration` | Only integration tests (testcontainers) |
| `make check` | `make lint typecheck test-unit` for Python and TS |
| `make lint` | `ruff format --check`, `ruff check`, `lint-imports`, `deptry`, `biome check`, `knip`, `opa fmt --diff`, `helm lint` |
| `make typecheck` | `mypy --strict` (Pydantic plugin) on libs/services/connectors, `tsc --noEmit` via turbo |
| `make test` | Unit + integration (testcontainers) + `opa test policies/` + web unit tests |
| `make test-e2e` | Playwright against `make dev` stack |
| `make gen` | Regenerates `openapi.json`, JSON Schemas, `@ar/api-client`, `ar_client`; CI fails if the tree changes |
| `make eval` | Runs golden eval suites against the configured models (`fake-llm` by default) |
| `make reset-db` | Drops and recreates the dev database, then `migrate seed` |
| `make kind-up` / `make kind-down` | kind cluster with the Helm chart (`values-dev.yaml`), gVisor runtime class (if available) and the Kubernetes sandbox driver |
| `make images` / `make images-bundle` | Build all images locally / export them for air-gapped installs |

## 3. Compose stack

`compose.yaml` profiles:
- `deps` (default for `make up`): postgres (pgvector image, `shared_preload_libraries=pg_stat_statements`), valkey, temporal (`temporal server start-dev` with SQLite persistence, UI on 8233), keycloak (realm import from `deploy/compose/keycloak/agentic-runtime-realm.json`), seaweedfs (S3, buckets `ar-files`, `ar-audit-archive` with Object Lock created by an init container), openbao (dev mode, KV v2 + Transit enabled by init script), opa (bundle polling `api`), squid (egress proxy), mailpit.
- `obs`: OTel collector, Prometheus, Tempo, Loki, Grafana, Langfuse (`make up OBS=1`).
- `scan`: ClamAV.
- `qdrant`: Qdrant on 6333/6334, only for working on or testing the optional qdrant retrieval adapter (`make up QDRANT=1`, then set `AR_VECTOR_BACKEND=qdrant` and `AR_QDRANT_URL=http://localhost:6333` in `.env`). Knowledge retrieval uses Postgres + pgvector by default; nothing else needs Qdrant.
- `apps`: also runs every app image (for testing images locally: `docker compose --profile apps up`).

Ports: [service-decomposition §6](../02-architecture/service-decomposition.md#6-ports-local-development).

## 4. Day-to-day

- Web: http://localhost:3000 → login redirects to Keycloak (8180) → use a seeded user.
- API docs: http://localhost:8000/api/docs (only `AR_ENV != prod`).
- Temporal UI: http://localhost:8233; Grafana: http://localhost:3001 and Langfuse: http://localhost:3100 (profile `obs`); Mailpit: http://localhost:8025.
- Using a real model: create a provider in **Admin → Models** pointing at an OpenAI-compatible endpoint, or set `AR_DEV_MODEL_BASE_URL`/`AR_DEV_MODEL_API_KEY` before `make seed` to seed it instead of `fake-llm`.
- Scripted fake-llm behaviour: `fake-llm` reads scenario files from `services/fake_llm/scenarios/*.yaml` (see [testing-strategy §4](../08-quality/testing-strategy.md#4-fake-llm)); default scenario echoes and calls tools when the message starts with `/tool <name> <json>`.
- New migration: `uv run alembic -c libs/ar_domain/alembic.ini revision --autogenerate -m "<area>_<change>"`, then hand-edit (RLS policies, grants) per [migrations](../04-data/migrations.md).
- Resetting state: `make reset-db`; `docker compose down -v` wipes everything.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| Login loops back to `/login` | Clock skew or wrong `AR_PUBLIC_URL`; ensure `http://localhost:3000` and that Keycloak realm imported (`docker compose logs keycloak`) |
| Runs stay `queued` | `runtime-worker` not running or Temporal not ready; check Temporal UI task queue `ar-runtime` pollers |
| Tool calls fail `sandbox_unavailable` | Docker socket not accessible to sandbox-manager; on macOS enable "Allow the default Docker socket" |
| `make gen` diff in CI | Run `make gen` and commit the generated files |
| Port in use | Override in `.env` (`AR_*_PORT`) and `compose.override.yaml` |
