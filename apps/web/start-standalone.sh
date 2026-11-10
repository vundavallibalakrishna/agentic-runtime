#!/usr/bin/env bash
# Production server for the standalone Next build. `next start` does not serve it.
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
cd "$root"
mkdir -p .next/standalone/apps/web/.next
rm -rf .next/standalone/apps/web/.next/static
cp -a .next/static .next/standalone/apps/web/.next/static
rm -rf .next/standalone/apps/web/public
cp -a public .next/standalone/apps/web/public
cd .next/standalone/apps/web
export PORT="${AR_WEB_HOST_PORT:-3000}"
export HOSTNAME="${HOSTNAME:-0.0.0.0}"
exec node server.js
