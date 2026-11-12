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
# Next binds the address in HOSTNAME. The shell sets HOSTNAME to the machine's name, so a
# default never applied and the server was not reachable on localhost. Listen on every
# interface, as the web image does.
export HOSTNAME="0.0.0.0"
exec node server.js
