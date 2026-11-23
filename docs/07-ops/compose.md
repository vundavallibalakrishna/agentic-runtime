# Compose install

Docker Compose is the install. One node, one `compose.yaml`, for development and for production. Profile `dev` starts the data plane for a process on the host. Profile `production` starts the product's core. A feature the customer uses is one more file (section 3a).

## 1. Layout

| Piece | Where |
|---|---|
| Services, networks, volumes | `compose.yaml` |
| Features a customer switches on | `compose.<feature>.yaml` (section 3a) |
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

## 3a. The core and the features

`docker compose --profile production up -d` starts the core: what a tenant needs to sign in, build agents, chat with tools, read documents, and run routines and evals.

| Core service | What it does |
|---|---|
| `api`, `web` | The product's API and screens |
| `worker` | Agent runs, routines, evals and housekeeping: the runtime worker and the system worker in one process |
| `ingest-worker` | Reads uploaded documents |
| `mcp-gateway` | Every tool call passes through it |
| `postgres`, `valkey`, `temporal`, `seaweedfs` | Data, shared state, the workflow engine, file bytes |

A feature is a file that starts the feature's services and tells the core where they are. Name the files in `COMPOSE_FILE` in `.env`, separated by `:`, so every `docker compose` command uses them:

```bash
COMPOSE_FILE=compose.yaml:compose.computers.yaml:compose.channels.yaml
```

| File | Starts | Switch it on when |
|---|---|---|
| `compose.computers.yaml` | `sandbox-manager`, `squid` | Agents run code, a shell or a browser in their own container. Build the image first: `docker build -f images/sandbox/Dockerfile -t ar-sandbox:dev .` |
| `compose.channels.yaml` | `channels` | People reach agents from Slack, Teams or email |
| `compose.connectors.yaml` | `mcp-sql`, `mcp-openapi` | The tenant uses SQL or OpenAPI connections |
| `compose.opa.yaml` | `opa` | A tenant writes its own Rego rules. Without it the product's own evaluator decides every tool call, with the same rules |
| `compose.vault.yaml` | `openbao` | Secrets are kept in a vault (`AR_SECRETS_BACKEND=vault`). The default keeps them encrypted in the database |
| `compose.model-gateway.yaml` | `model-gateway` | A model provider has no address of its own. A provider registered with its address is called there directly |
| `compose.split-workers.yaml` | `runtime-worker`, `system-worker` in place of `worker` | The install scales agent runs apart from routines and evals |
| `compose.airgap.yaml` | nothing new | The install has no route to the internet (section 6). Use it with `compose.computers.yaml` |

Without `compose.computers.yaml` the install has no computers: a tool that needs one answers "Computers are not switched on for this install" and nothing runs in its place.

### Memory

Measured by `scripts/compose_install.sh` in CI on 21 November 2026 (commit `9a469aac`, a 16 GB runner), idle after one chat turn and after the worker had settled. Parsing a large document adds to `ingest-worker` (939 MiB was seen while a 114-page PDF was read), and each running computer is a container of its own.

| Core service | Memory |
|---|---|
| `api` | 385 MiB |
| `worker` | 275 MiB |
| `postgres` | 249 MiB |
| `ingest-worker` | 182 MiB |
| `mcp-gateway` | 172 MiB |
| `seaweedfs` | 111 MiB |
| `temporal` | 99 MiB |
| `web` | 52 MiB |
| `valkey` | 18 MiB |
| **Core total** | **about 1.5 GiB** |

Run apart (`compose.split-workers.yaml`), `runtime-worker` measured 275 MiB and `system-worker` 350 MiB.

| Feature service | Memory |
|---|---|
| `channels` | 123 MiB |
| `model-gateway` | 120 MiB |
| `mcp-sql` | 119 MiB |
| `mcp-openapi` | 101 MiB |
| `openbao` | 19 MiB |
| `opa` | 14 MiB |
| `clamav` (profile `scan`, measured on a laptop) | about 1 GiB |
| `sandbox-manager`, `squid` | not measured |

Size a machine for the core at 4 GB of memory, and 8 GB when documents are parsed often or the virus scanner is on.

Every file together is the full install. `scripts/compose_install.sh` starts the core, proves a chat turn on it, prints each container's memory, then starts every feature except computers and proves a tool call decided by OPA. The plan and the reasons are in [small-install](../09-plan/small-install.md).

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

Network `agentic-runtime_sandbox` is internal and is used by the computers feature (`compose.computers.yaml`). Sandbox containers join it and no other network. `sandbox-manager`, which waits for a computer to start, and `mcp-gateway`, which runs tools on it, join it as well as the app network; no other service does. Their HTTP and HTTPS go through Squid (`AR_SANDBOX_EGRESS_PROXY`, default `http://squid:3128`) with the sandbox token. The docker driver drops all capabilities, sets a read-only root with tmpfs for `/tmp`, `/workspace` and `/home/sandbox`, and sets cpu, memory and pid limits. `sandbox-manager` is the only service that mounts the docker socket, and the only creator of those containers.

`AR_SANDBOX_ALLOW_UNISOLATED` is not required for that default. It allows a host process instead of a container.

Air gap:

```bash
docker compose -f compose.yaml -f compose.computers.yaml -f compose.airgap.yaml --profile production up -d
```

`app` becomes internal. Squid is the only service on an external network. Put allowed model hosts in `deploy/compose/squid/allowlist.txt`, one domain per line. `api`, `model-gateway` and `runtime-worker` then use the proxy.

## 7. Architecture invariants

- `sandbox-manager` is the only creator of sandbox containers, and it uses the docker driver.
- An install without `sandbox-manager` has no computers. It never runs a computer's work in another process.
- One install decides policy one way: every process uses the OPA server when its address is set, and the built-in evaluator when it is not.
- `mcp-gateway` is the only tool path.
- Temporal runs one activity per step.
- Postgres is the source of truth.
