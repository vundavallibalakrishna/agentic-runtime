#!/bin/sh
# Logical backup of the install databases. Cron can call this once a day.
# Each database is a custom-format pg_dump. Passwords stay inside the container.
set -eu

dest=${1:-./backups/agentic-runtime-$(date -u +%Y%m%dT%H%M%SZ)}
mkdir -p "$dest"

dump() {
  database=$1
  docker compose exec -T postgres pg_dump -U postgres -d "$database" -Fc >"$dest/$database.dump"
}

dump agentic_runtime
dump temporal
dump temporal_visibility
echo "wrote ${dest}"
