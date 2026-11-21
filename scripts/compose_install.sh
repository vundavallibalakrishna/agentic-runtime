#!/bin/sh
# Production profile from scratch, then an upgrade from a main-style volume.
# Does not print passwords.
set -eu
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
fi
uv run python scripts/dev_keys.py

set -a
# shellcheck disable=SC1091
. ./.env
set +a

# The production profile is the core install. The smoke adds a test-only model
# overlay so the chat turn has an OpenAI-compatible server. That file is not
# part of compose.yaml.
export AR_ENV=dev
compose="docker compose -f compose.yaml -f tests/compose/ci-model.yaml --profile production"

$compose up -d --build

AR_ENV=dev \
  AR_DEV_MODEL_BASE_URL=http://ci-model:8099/v1 \
  AR_DEV_MODEL_NAME=ci-model \
  AR_LLM_MODEL=ci-chat \
  uv run python scripts/seed.py
$compose restart runtime-worker >/dev/null
uv run python scripts/compose_smoke.py

# What the core costs. The table in docs/07-ops/compose.md comes from this output.
echo "core install: containers and memory"
$compose ps --format 'table {{.Service}}\t{{.Status}}'
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'

# Every feature on: the services the core leaves out start, and a tool call is decided
# by OPA. Computers are not started here: their image is built separately.
echo "every feature on"
features="-f compose.yaml -f tests/compose/ci-model.yaml -f compose.opa.yaml -f compose.vault.yaml \
  -f compose.channels.yaml -f compose.connectors.yaml -f compose.model-gateway.yaml"
# shellcheck disable=SC2086
docker compose $features --profile production up -d --build --wait
AR_SMOKE_OPA=1 AR_SMOKE_ONLY=policy uv run python scripts/compose_smoke.py
# shellcheck disable=SC2086
docker compose $features --profile production ps --format 'table {{.Service}}\t{{.Status}}'
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'

echo "upgrade from a main-style volume"
upgrade_volume=ar-main-style-pg
docker rm -f ar-main-style-pg >/dev/null 2>&1 || true
docker volume rm -f "$upgrade_volume" >/dev/null 2>&1 || true
docker volume create "$upgrade_volume" >/dev/null
docker run -d --name ar-main-style-pg \
  --network agentic-runtime_app \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD \
  -e POSTGRES_DB=agentic_runtime \
  -e AR_DB_OWNER_PASSWORD \
  -e AR_DB_PLATFORM_PASSWORD \
  -e AR_DB_APP_PASSWORD \
  -e AR_DB_READONLY_PASSWORD \
  -v "$upgrade_volume":/var/lib/postgresql \
  -v "$PWD/tests/fixtures/main-style-init-roles.sh:/docker-entrypoint-initdb.d/01-roles.sh:ro" \
  pgvector/pgvector:0.8.7-pg18-trixie >/dev/null

wait_ready() {
  i=0
  while [ "$i" -lt 40 ]; do
    if docker exec ar-main-style-pg pg_isready -U postgres -d agentic_runtime >/dev/null 2>&1; then
      return 0
    fi
    i=$((i + 1))
    sleep 2
  done
  echo "main-style postgres did not become ready" >&2
  exit 1
}

wait_ready
docker stop ar-main-style-pg >/dev/null
docker rm ar-main-style-pg >/dev/null
docker run -d --name ar-main-style-pg \
  --network agentic-runtime_app \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD \
  -e POSTGRES_DB=agentic_runtime \
  -v "$upgrade_volume":/var/lib/postgresql \
  pgvector/pgvector:0.8.7-pg18-trixie >/dev/null
wait_ready

docker compose -f compose.yaml -f tests/compose/ci-model.yaml --profile production run --rm --no-deps \
  -e POSTGRES_HOST=ar-main-style-pg \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD \
  -e POSTGRES_DB=agentic_runtime \
  -e AR_DB_RECONCILE=run \
  reconcile-roles

docker exec ar-main-style-pg psql -U postgres -d agentic_runtime -tA -v ON_ERROR_STOP=1 \
  -c "SELECT rolname FROM pg_roles WHERE rolname = 'ar_temporal' AND rolsuper = false AND rolbypassrls = false" \
  | grep -q ar_temporal
docker exec ar-main-style-pg psql -U postgres -d postgres -tA -v ON_ERROR_STOP=1 \
  -c "SELECT datname FROM pg_database WHERE datname IN ('temporal','temporal_visibility') ORDER BY 1" \
  | grep -q temporal_visibility
echo "old volume reconciled"
docker rm -f ar-main-style-pg >/dev/null
docker volume rm -f "$upgrade_volume" >/dev/null
