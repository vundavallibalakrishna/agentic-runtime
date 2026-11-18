#!/bin/sh
# Idempotent Temporal schema setup. The password stays in SQL_PASSWORD.
set -eu

export SQL_PLUGIN=postgres12
export SQL_HOST="${POSTGRES_SEEDS:?POSTGRES_SEEDS is required}"
export SQL_PORT="${DB_PORT:-5432}"
export SQL_USER="${POSTGRES_USER:?POSTGRES_USER is required}"
export SQL_PASSWORD="${POSTGRES_PWD:?POSTGRES_PWD is required}"

apply() {
  db=$1
  dir=$2
  err=/tmp/temporal-schema.err
  n=0
  while [ "$n" -lt 60 ]; do
    if temporal-sql-tool --db "$db" setup-schema -v 0.0 >"$err" 2>&1 \
      || grep -q "already exists" "$err"; then
      if temporal-sql-tool --db "$db" update-schema -d "$dir" >"$err" 2>&1; then
        rm -f "$err"
        return 0
      fi
    fi
    n=$((n + 1))
    sleep 2
  done
  echo "temporal schema update failed for ${db}" >&2
  exit 1
}

apply temporal /etc/temporal/schema/postgresql/v12/temporal/versioned
apply temporal_visibility /etc/temporal/schema/postgresql/v12/visibility/versioned
