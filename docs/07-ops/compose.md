# Compose install

Docker Compose is the install. One node, one `compose.yaml`, for development and for production. Profile `dev` starts the data plane for a process on the host. Profile `production` starts the product.

## 1. Layout

| Piece | Where |
|---|---|
| Services, networks, volumes | `compose.yaml` |
| Air-gap override | `compose.airgap.yaml` |
| Postgres role init | `deploy/compose/postgres/init-roles.sh` |
| Temporal schema and server | `deploy/compose/temporal/` |
| Squid allowlist | `deploy/compose/squid/allowlist.txt` |
| Passwords and keys | `.env`, written by `scripts/dev_keys.py` |

`scripts/dev_keys.py` fills `AR_DB_OWNER_PASSWORD`, `AR_DB_PLATFORM_PASSWORD`, `AR_DB_APP_PASSWORD`, `AR_DB_READONLY_PASSWORD`, `AR_DB_TEMPORAL_PASSWORD` and `POSTGRES_PASSWORD`. Staging and production refuse a placeholder or a role name. `AR_ENV=prod` with password sign-in needs `AR_AUTH_MODE=password` and `AR_PASSWORD_LOGIN=true`. OIDC needs `AR_OIDC_ISSUER` and `AR_OIDC_CLIENT_ID`. A model is whatever provider the tenant registers. `services/fake_llm` is a test double and is not a Compose service. Loopback and wildcard egress default off; a local checkout sets them in `.env`. Telemetry is off until `AR_OTEL_EXPORTER_OTLP_ENDPOINT` is set.

## 2. Startup order

1. `postgres` is healthy.
2. `reconcile-roles` finishes. It creates or updates `ar_owner`, `ar_app`, `ar_platform`, `ar_readonly` and `ar_temporal`, and the `temporal` and `temporal_visibility` databases. An old volume is updated here.
3. `migrate` finishes. It runs Alembic to head.
4. `temporal-schema` finishes. `temporalio/admin-tools:1.32.1` applies the Postgres schema.
5. `temporal` is healthy. One `temporalio/server:1.32.1` process uses those databases. `AR_TEMPORAL_NUM_HISTORY_SHARDS` defaults to 4 and is fixed for the life of the databases.
6. The app services start. `/readyz` stays unready until `alembic_version` is the head.

Long-running services use `restart: unless-stopped`, named volumes, and json-file logs capped at 10m by 3 files. Published ports bind to `127.0.0.1` except the web UI and the API.

## 3. Commands

```bash
cp .env.example .env
uv run python scripts/dev_keys.py
docker compose --profile production up -d --build
```

Development data plane, with the apps on the host:

```bash
make up
make migrate
make seed
```

## 4. Upgrade

```bash
bash scripts/compose_upgrade.sh
```

That pulls images, removes the one-shot role, migrate and Temporal schema containers, and starts the stack again. `reconcile-roles` runs before migrate, including on a volume created by an older init script.

Do not change `AR_TEMPORAL_NUM_HISTORY_SHARDS` after the first successful Temporal start.

## 5. Backup and restore

```bash
bash scripts/backup_postgres.sh ./backups/nightly
docker compose --profile production stop
bash scripts/restore_postgres.sh ./backups/nightly
docker compose --profile production up -d
```

The backup is three `pg_dump -Fc` files: `agentic_runtime`, `temporal` and `temporal_visibility`. A cron line can call `scripts/backup_postgres.sh` with an absolute directory. There is no database operator.

## 6. Networks and egress

Network `agentic-runtime_app` carries the product. Model calls leave from `api` and `runtime-worker` on that network.

Network `agentic-runtime_sandbox` is internal. Sandbox containers join it and no other network. Their HTTP and HTTPS go through Squid (`AR_SANDBOX_EGRESS_PROXY`, default `http://squid:3128`) with the sandbox token. The docker driver drops all capabilities, sets a read-only root with tmpfs for `/tmp`, `/workspace` and `/home/sandbox`, and sets cpu, memory and pid limits. `sandbox-manager` is the only service that mounts the docker socket, and the only creator of those containers.

`AR_SANDBOX_ALLOW_UNISOLATED` is not required for that default. It allows a host process instead of a container.

Air gap:

```bash
docker compose -f compose.yaml -f compose.airgap.yaml --profile production up -d
```

`app` becomes internal. Squid is the only service on an external network. Put allowed model hosts in `deploy/compose/squid/allowlist.txt`, one domain per line. `api`, `model-gateway` and `runtime-worker` then use the proxy.

## 7. Architecture invariants

- `sandbox-manager` is the only creator of sandbox containers, and it uses the docker driver.
- `mcp-gateway` is the only tool path.
- Temporal runs one activity per step.
- Postgres is the source of truth.
