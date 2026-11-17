#!/bin/sh
# Start the CI database with passwords from scripts/dev_keys.py.
# The same generator fills compose, kind and a developer .env.
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
uv run python scripts/dev_keys.py
set -a
# shellcheck disable=SC1091
. ./.env
set +a
docker rm -f ci-postgres >/dev/null 2>&1 || true
docker run -d --name ci-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD \
  -e POSTGRES_DB=agentic_runtime \
  -p 5432:5432 \
  pgvector/pgvector:0.8.7-pg18-trixie >/dev/null
ready=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
  if docker exec ci-postgres pg_isready -U postgres -d agentic_runtime >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  docker logs ci-postgres >&2 || true
  exit 1
fi
