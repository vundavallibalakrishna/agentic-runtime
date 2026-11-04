# M23 run guide

Use a database that is not the operator's compose Postgres. The steps below use ports `55440` (platform) and `55432` (customer) and API port `18123`.

## Platform database

```bash
docker run -d --name m23-platform-pg \
  -e POSTGRES_USER=ar_owner -e POSTGRES_PASSWORD=ar_owner \
  -e POSTGRES_DB=agentic_runtime -p 55440:5432 \
  -v "$PWD/deploy/compose/postgres/init.sql:/docker-entrypoint-initdb.d/00-init.sql:ro" \
  pgvector/pgvector:0.8.7-pg18-trixie
```

Wait until it accepts connections, then from the repository root:

```bash
AR_DATABASE_URL=postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:55440/agentic_runtime \
  uv run alembic -c libs/ar_domain/alembic.ini upgrade head
```

Seed with the host port set so settings do not rewrite the URL back to 5432:

```bash
AR_PG_HOST_PORT=55440 \
AR_DATABASE_URL=postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:55440/agentic_runtime \
  uv run --no-env-file python scripts/seed.py
```

Run the API with `AR_PG_HOST_PORT=55440`, `AR_PORT=18123`, `AR_TEMPORAL_ADDRESS=127.0.0.1:1` and `uv run --no-env-file`. Point Temporal at an unused port so turns run in-process instead of the operator's Temporal. Generate `AR_DB_ENCRYPTION_KEYS` at runtime. Do not write `AR_CERT_LLM_API_KEY` into a file. The provider is created through `POST /api/v1/model-providers` with the key read from the environment.

## Customer database

```bash
docker run -d --name m23-customer-pg \
  -e POSTGRES_USER=loader -e POSTGRES_PASSWORD=loader \
  -e POSTGRES_DB=analysis -p 55432:5432 \
  pgvector/pgvector:0.8.7-pg18-trixie
```

Load a public CSV as the loader, then grant `SELECT` to a separate analyst role. Connect the agent with the analyst role. The platform URL must not be this database.

## What to click

1. Sign in as `admin@dev.local`.
2. Open Connections. Save a database. The connection string is not shown again. Test connection.
3. Open an agent. Turn on Database tools and set a row limit. Save a JSON schema.
4. In chat, attach a CSV and an xlsx and ask for a count, a chart and a downloadable file.

Restart the API process and reload Connections. The database row is still there.

Screenshots from Playwright go to `docs/testing/m23/`.
