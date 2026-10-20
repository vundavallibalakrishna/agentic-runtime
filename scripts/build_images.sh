#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
services=(api runtime system model_gateway mcp_gateway sandbox_manager channels mcp_sql mcp_openapi fake_llm)
for service in "${services[@]}"; do
  docker build -f images/python-service.Dockerfile --build-arg SERVICE="$service" -t "ar-${service//_/-}:dev" .
done
docker build -f images/python-service.Dockerfile --build-arg SERVICE="domain" -t ar-migrate:dev .
docker build -f images/web.Dockerfile -t ar-web:dev .
docker build -f images/sandbox/Dockerfile -t ar-sandbox:dev .
docker build -f images/ingest/Dockerfile -t ar-ingest:dev .
docker build -f images/squid/Dockerfile -t ar-squid:dev .
