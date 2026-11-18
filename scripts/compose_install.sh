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

# The production profile is the install. Fake-llm is accepted in dev and ci, so
# the smoke keeps AR_ENV=dev and requires Temporal. A prod env points the model
# alias at a real provider and sets AR_OIDC_ISSUER.
export AR_ENV=dev
export AR_TEMPORAL_REQUIRED=true

docker compose --profile production up -d --build

AR_ENV=dev AR_FAKE_LLM_BASE_URL=http://fake-llm:8099/v1 uv run python scripts/seed.py
# The seeded provider is kind fake, which the durable turn refuses. Point it at
# the same fake-llm server as an OpenAI-compatible recorded model, then reload.
docker compose --profile production exec -T postgres \
  psql -U postgres -d agentic_runtime -v ON_ERROR_STOP=1 \
  -c "UPDATE model_providers SET kind = 'openai_compatible' WHERE name = 'fake-llm'"
docker compose --profile production restart runtime-worker >/dev/null
uv run python scripts/compose_smoke.py

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

docker compose --profile production run --rm --no-deps \
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
