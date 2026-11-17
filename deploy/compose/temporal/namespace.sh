#!/bin/sh
# Register the Temporal namespace once the server is serving. Idempotent.
set -eu

ns="${TEMPORAL_NAMESPACE:-default}"
i=0
while [ "$i" -lt 30 ]; do
  if temporal --address temporal:7233 operator namespace describe --namespace "$ns" >/dev/null 2>&1; then
    exit 0
  fi
  if temporal --address temporal:7233 operator namespace create --namespace "$ns" --retention 72h >/dev/null 2>&1; then
    exit 0
  fi
  i=$((i + 1))
  sleep 2
done
echo "temporal namespace was not created" >&2
exit 1
