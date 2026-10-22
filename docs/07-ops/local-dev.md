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
| `make up` / `make down` | Start/stop dependency containers from `compose.yaml` (profile `deps`; add `OBS=1`, `SCAN=1`, `QDRANT=1` for the optional `obs`, `scan`, `qdrant` profiles). `make up` waits until the health checks pass before it returns, so `make migrate` does not race Postgres |
| `make migrate` | `uv run alembic -c libs/ar_domain/alembic.ini upgrade head` and seeds Keycloak realm (import is automatic on first start) |
| `make seed` | `uv run python scripts/seed.py`: tenant `dev` (plan `enterprise`, matching the Keycloak organization `dev`), users `admin@dev.local` (tenant_admin), `builder@dev.local` (builder, tool_owner, knowledge_manager), `member@dev.local` (member), `approver@dev.local` (approver), all with password `dev-password` (defined in the realm export); model provider `fake-llm` with aliases `reasoning`, `fast`, `vision`, `embed`, `rerank`; team `everyone`; published agent `assistant`. Sample knowledge and the Helpdesk agent arrive with later milestones. |
| `make ports-check` | Reads `.env` host ports, rewrites localhost URLs so they use the same ports, and exits non-zero when a port is already taken. The message names the variable to change. |
| `make dev` | `make ports-check`, then `make up migrate seed` (idempotent), then all app processes via `honcho` (`Procfile.dev`): api, runtime-worker, system-worker, ingest-worker, model-gateway, mcp-gateway, sandbox-manager (Docker driver), channels, mcp-sql, mcp-openapi, fake-llm, web (`pnpm --filter @ar/web dev`). `make dev AUTO_PORTS=1` moves busy host ports onto free ports and updates the URLs before compose starts. |
| `make dev-min` | Same preflight, then only api, runtime-worker, system-worker, model-gateway, mcp-gateway, fake-llm, web (enough for chat + tools) |
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
- `deps` (default for `make up`): postgres (pgvector image, `shared_preload_libraries=pg_stat_statements`; the data volume is `/var/lib/postgresql`, which is the Postgres 18 data directory), valkey, temporal (`temporal server start-dev` with SQLite persistence, UI on 8233), keycloak (realm import from `deploy/compose/keycloak/agentic-runtime-realm.json`, login theme `agentic`, plain HTTP for local dev), seaweedfs (S3, buckets `ar-files`, `ar-audit-archive` with Object Lock created by an init container), openbao (dev mode, KV v2 + Transit enabled by init script), opa (serves `policies/rego` and ignores `policies/fixtures`, whose JSON files are cross-check input rather than Rego data), squid (egress proxy), mailpit.
- `obs`: OTel collector, Prometheus, Tempo, Loki, Grafana, Langfuse (`make up OBS=1`).
- `scan`: ClamAV.
- `qdrant`: Qdrant on 6333/6334, only for working on or testing the optional qdrant retrieval adapter (`make up QDRANT=1`, then set `AR_VECTOR_BACKEND=qdrant` and `AR_QDRANT_URL=http://localhost:6333` in `.env`). Knowledge retrieval uses Postgres + pgvector by default; nothing else needs Qdrant.
- `apps`: also runs every app image (for testing images locally: `docker compose --profile apps up`).

Ports: [service-decomposition §6](../02-architecture/service-decomposition.md#6-ports-local-development). Every host port is an env var with that number as the default. See [Host ports](#5-host-ports).

## 4. Day-to-day

- Web: http://localhost:3000. The sign-in page lists the four seeded users for dev login, and **Continue with SSO** opens Keycloak. Organisations are on, so Keycloak asks for the username and then the password. Password `dev-password`. The dev realm allows plain HTTP on localhost.
- API docs: http://localhost:8000/api/docs (only `AR_ENV != prod`).
- Temporal UI: http://localhost:8233; Grafana: http://localhost:3001 and Langfuse: http://localhost:3100 (profile `obs`); Mailpit: http://localhost:8025.
- Using a real model: create a provider in **Admin → Models** pointing at an OpenAI-compatible endpoint, or set `AR_DEV_MODEL_BASE_URL`/`AR_DEV_MODEL_API_KEY` before `make seed` to seed it instead of `fake-llm`.
- Scripted fake-llm behaviour: `fake-llm` reads scenario files from `services/fake_llm/scenarios/*.yaml` (see [testing-strategy §4](../08-quality/testing-strategy.md#4-fake-llm)); default scenario echoes and calls tools when the message starts with `/tool <name> <json>`.
- New migration: `uv run alembic -c libs/ar_domain/alembic.ini revision --autogenerate -m "<area>_<change>"`, then hand-edit (RLS policies, grants) per [migrations](../04-data/migrations.md).
- Resetting state: `make reset-db`; `docker compose down -v` wipes everything.

## 5. Host ports

`compose.yaml` publishes `${AR_PG_HOST_PORT:-5432}` (and the same pattern for every other host port). Database container ports stay on the image default. App processes listen on the published port (`AR_PORT` for the API). `make ports-check` copies a changed host port into the matching localhost URL in `.env`:

| Set this | Also updates |
|---|---|
| `AR_PG_HOST_PORT` | `AR_DATABASE_URL` when the host is localhost |
| `AR_VALKEY_HOST_PORT` | `AR_VALKEY_URL` |
| `AR_TEMPORAL_HOST_PORT` | `AR_TEMPORAL_ADDRESS` |
| `AR_PORT` | API listen port, `AR_API_INTERNAL_URL`, and `API_PROXY_URL` (the web dev rewrite) |
| `AR_WEB_HOST_PORT` | `AR_PUBLIC_URL` and `next dev --port` |
| `AR_FAKE_LLM_HOST_PORT` | fake-llm listen port and the seeded base URL |
| `AR_KEYCLOAK_HOST_PORT` | `AR_OIDC_ISSUER` when it points at localhost |
| `AR_S3_HOST_PORT` | `AR_S3_ENDPOINT` and `AR_S3_PUBLIC_ENDPOINT` |
| `AR_VAULT_HOST_PORT` | `AR_VAULT_ADDR` |

The full list, including Mailpit, Squid, OPA, Grafana and the worker health ports, is in `.env.example` and [environments §3.3](environments.md#33-local-host-ports). A remote URL (host other than `localhost` or `127.0.0.1`) is left alone. A localhost URL is rewritten to the host port, including back to the default when the host port is the default again. An empty value in `.env` is ignored and the setting's default is used, so a copied `.env.example` does not fail validation on a blank number.

`make dev AUTO_PORTS=1` treats a port published by this compose project as free, so a second start does not keep walking the port number. It also moves `AR_MG_PORT` (model gateway, 8001) and `AR_SYSTEM_HOST_PORT` (system worker, 8013) when those are taken. `scripts/dev_keys.py` writes `AR_DB_ENCRYPTION_KEYS` as a quoted JSON keyring `{"k1":"<standard base64>"}` and `AR_SESSION_ENCRYPTION_KEY` as standard base64. Alembic reads `AR_DATABASE_URL` from the environment or from `.env`.

Example when Postgres, Valkey, Temporal and the API are already taken:

```bash
# .env
AR_PG_HOST_PORT=15432
AR_VALKEY_HOST_PORT=16379
AR_TEMPORAL_HOST_PORT=17233
AR_PORT=18000
```

Then `make dev`. Or skip the edits: `make dev AUTO_PORTS=1`.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| Login loops back to `/login` | Clock skew or wrong `AR_PUBLIC_URL`; ensure `http://localhost:3000` and that Keycloak realm imported (`docker compose logs keycloak`) |
| Runs stay `queued` | `runtime-worker` not running or Temporal not ready; check Temporal UI task queue `ar-runtime` pollers |
| Tool calls fail `sandbox_unavailable` | Docker socket not accessible to sandbox-manager; on macOS enable "Allow the default Docker socket" |
| `make gen` diff in CI | Run `make gen` and commit the generated files |
| Port in use | `make ports-check` prints the variable (`AR_PG_HOST_PORT`, `AR_VALKEY_HOST_PORT`, `AR_TEMPORAL_HOST_PORT`, `AR_PORT`, `AR_MG_PORT`, `AR_SYSTEM_HOST_PORT`, …). Set it in `.env` or run `make dev AUTO_PORTS=1`. One assignment updates the published port and the localhost URL. |
| `NoSuchModuleError: driver` from Alembic | `AR_DATABASE_URL` was empty. Run `make bootstrap` so `.env` exists, then `make migrate` (it loads `.env`). |
| Postgres exits with an unused data directory | The Postgres 18 volume must be mounted at `/var/lib/postgresql`, not `/var/lib/postgresql/data`. `compose.yaml` already does this. Recreate the volume if an older container left it on the wrong path. |
| `max_json_body_bytes` validation error on an empty string | Empty assignments in `.env` are ignored. Pull the current settings code and restart. |
| `NoReferencedTableError` on `secret_refs` during seed | `make seed` imports every model module before it opens a session. Update and run `make seed` again. |
| `Incorrect padding` from the encryption key | `AR_DB_ENCRYPTION_KEYS` must be a JSON keyring of standard base64. Run `make bootstrap` again (or delete the placeholder and let `scripts/dev_keys.py` rewrite it). |
| Keycloak says HTTPS required | The dev realm uses `sslRequired: none` and the compose service disables the hostname HTTPS check. Re-import the realm (`docker compose down` the keycloak volume, then `make up`) if an older realm is still stored. |
| Keycloak asks to update account information | The seeded users need a first and last name. Re-import the realm from `deploy/compose/keycloak/agentic-runtime-realm.json`. |
| `/login?error=tenant_not_found` after a correct password | The API callback must exchange the code and map the Keycloak organisation `dev` (or an `@dev.local` address) onto the demo tenant. Check `AR_OIDC_ISSUER`, `AR_OIDC_CLIENT_SECRET` (default `ar-web-dev-secret`) and that the redirect URI matches `AR_PUBLIC_URL`. |
