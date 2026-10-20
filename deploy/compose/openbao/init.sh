#!/bin/sh
set -eu
export BAO_ADDR=http://127.0.0.1:8200
export BAO_TOKEN="${BAO_DEV_ROOT_TOKEN_ID:-dev-root-token}"
i=0
until bao status >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 30 ]; then
    echo "openbao did not start" >&2
    exit 1
  fi
  sleep 1
done
bao secrets enable -path=secret kv-v2 || true
bao secrets enable transit || true
echo "openbao kv and transit enabled"
