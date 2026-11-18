#!/bin/sh
# Restore a directory written by scripts/backup_postgres.sh.
# Stop the app first: docker compose --profile production stop.
set -eu

src=${1:?usage: scripts/restore_postgres.sh BACKUP_DIR}

restore() {
  database=$1
  test -f "$src/$database.dump"
  docker compose exec -T postgres pg_restore -U postgres -d "$database" --clean --if-exists --no-owner \
    <"$src/$database.dump"
}

restore agentic_runtime
restore temporal
restore temporal_visibility
echo "restored ${src}"
