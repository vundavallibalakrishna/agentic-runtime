#!/bin/sh
# Pull images and apply role, schema and Temporal changes before the apps restart.
# reconcile_roles updates an existing volume. numHistoryShards is not changed here.
set -eu

profile=${1:-production}
docker compose --profile "$profile" pull
docker compose --profile "$profile" rm -f -s reconcile-roles migrate temporal-schema >/dev/null 2>&1 || true
docker compose --profile "$profile" up -d --build
