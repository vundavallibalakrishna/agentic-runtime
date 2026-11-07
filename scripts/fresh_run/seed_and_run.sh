#!/usr/bin/env bash
# Seed a tenant of the caller's choosing and run the fresh-tenant release gate against a
# stack that is already up. A convenience wrapper over scripts/seed_tenant.py and
# scripts/fresh_run/fresh_run.mjs — see scripts/fresh_run/README.md.
#
# No secret is baked in: the admin password and the model key are read from files named by
# the environment. Required environment:
#   AR_FRESH_ADMIN_PASSWORD_FILE  file holding the new admin's password
#   AR_FRESH_MODEL_BASE_URL       the OpenAI-compatible model endpoint
#   AR_FRESH_MODEL_KEY_FILE       file holding the model key
#   AR_FRESH_CHAT_MODEL           upstream chat model id
#   AR_FRESH_EMBED_MODEL          upstream embedding model id
# Optional: AR_FRESH_WEB (default http://localhost:3000), AR_FRESH_OUT, AR_FRESH_SECOND_EMAIL,
#   --skip-seed to drive an already-seeded tenant.
#
#   scripts/fresh_run/seed_and_run.sh --slug acme --name "Acme" \
#       --admin-email ada@acme.example --admin-name "Ada Lovelace"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SKIP_SEED=0
SLUG="" NAME="" ADMIN_EMAIL="" ADMIN_NAME=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-seed) SKIP_SEED=1; shift ;;
    --slug) SLUG="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --admin-email) ADMIN_EMAIL="$2"; shift 2 ;;
    --admin-name) ADMIN_NAME="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

: "${AR_FRESH_ADMIN_PASSWORD_FILE:?set AR_FRESH_ADMIN_PASSWORD_FILE}"
: "${AR_FRESH_MODEL_BASE_URL:?set AR_FRESH_MODEL_BASE_URL}"
: "${AR_FRESH_MODEL_KEY_FILE:?set AR_FRESH_MODEL_KEY_FILE}"
: "${AR_FRESH_CHAT_MODEL:?set AR_FRESH_CHAT_MODEL}"
: "${AR_FRESH_EMBED_MODEL:?set AR_FRESH_EMBED_MODEL}"

cd "$ROOT"

if [[ "$SKIP_SEED" -eq 0 ]]; then
  : "${SLUG:?--slug is required unless --skip-seed}"
  : "${NAME:?--name is required unless --skip-seed}"
  : "${ADMIN_EMAIL:?--admin-email is required unless --skip-seed}"
  : "${ADMIN_NAME:?--admin-name is required unless --skip-seed}"
  if [[ "$SLUG" == "dev" ]]; then
    echo "the gate must run on a tenant that is not called 'dev'" >&2
    exit 2
  fi
  echo "seeding tenant $SLUG ($NAME) with admin $ADMIN_EMAIL"
  uv run python scripts/seed_tenant.py \
    --slug "$SLUG" --name "$NAME" \
    --admin-email "$ADMIN_EMAIL" --admin-name "$ADMIN_NAME" \
    < "$AR_FRESH_ADMIN_PASSWORD_FILE"
fi

AR_FRESH_ADMIN_EMAIL="${AR_FRESH_ADMIN_EMAIL:-$ADMIN_EMAIL}" \
  node scripts/fresh_run/fresh_run.mjs
