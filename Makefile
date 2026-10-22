# Agentic Runtime — local entry points. Spec: docs/07-ops/local-dev.md
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

OBS ?= 0
SCAN ?= 0
QDRANT ?= 0
AUTO_PORTS ?= 0
DEV_MIN ?= 0
COMPOSE := docker compose -f compose.yaml
PROFILES := --profile deps
ifeq ($(OBS),1)
PROFILES += --profile obs
endif
ifeq ($(SCAN),1)
PROFILES += --profile scan
endif
ifeq ($(QDRANT),1)
PROFILES += --profile qdrant
endif

PY_PKGS := libs/ar_common libs/ar_contracts libs/ar_domain libs/ar_connector_sdk libs/ar_testing libs/ar_client \
	services/api services/runtime services/system services/ingest services/model_gateway services/mcp_gateway \
	services/sandbox_manager services/sandbox_agent services/channels services/fake_llm \
	connectors/mcp_sql connectors/mcp_openapi

.PHONY: help bootstrap up down migrate seed ports-check dev dev-min fmt lint typecheck test \
	test-unit test-integration test-e2e check gen eval reset-db kind-up kind-down images \
	images-bundle deptry

help:
	@echo "make bootstrap | up | down | migrate | seed | ports-check | dev | check | gen"
	@echo "make dev AUTO_PORTS=1    # move busy host ports and rewrite localhost URLs"

bootstrap:
	uv sync --all-packages --all-groups --all-extras
	pnpm install
	pnpm exec lefthook install || true
	@if [ ! -f .env ]; then cp .env.example .env; fi
	uv run python scripts/dev_keys.py

up:
	$(COMPOSE) $(PROFILES) up -d --wait --wait-timeout 180

down:
	$(COMPOSE) --profile deps --profile obs --profile scan --profile qdrant --profile apps down

migrate:
	@set -a; [ -f .env ] && . ./.env; set +a; \
	if ls libs/ar_domain/src/ar_domain/migrations/versions/*.py >/dev/null 2>&1; then \
		uv run alembic -c libs/ar_domain/alembic.ini upgrade head; \
	else \
		echo "not available until M1-T02"; \
	fi

seed:
	uv run python scripts/seed.py

ports-check:
	AUTO_PORTS="$(AUTO_PORTS)" DEV_MIN="$(DEV_MIN)" OBS="$(OBS)" SCAN="$(SCAN)" QDRANT="$(QDRANT)" \
		uv run python scripts/host_ports.py

dev: ports-check
	$(MAKE) up migrate seed
	uv run honcho start -f Procfile.dev

dev-min:
	$(MAKE) ports-check DEV_MIN=1
	$(MAKE) up migrate seed
	uv run honcho start -f Procfile.dev-min

fmt:
	uv run ruff format .
	uv run ruff check --fix .
	pnpm exec biome check --write .

lint:
	uv run ruff format --check .
	uv run ruff check .
	uv run lint-imports
	$(MAKE) deptry
	pnpm exec biome check .
	pnpm exec knip
	opa fmt --diff policies/
	helm lint deploy/helm/agentic-runtime

deptry:
	@fail=0; \
	for pkg in $(PY_PKGS); do \
		echo "deptry $$pkg"; \
		if ! (cd "$$pkg" && uv run deptry .); then fail=1; fi; \
	done; \
	exit $$fail

typecheck:
	uv run mypy
	pnpm exec turbo run typecheck

test-unit:
	uv run pytest -m "not integration and not e2e" -q --cov
	pnpm exec turbo run test

test-integration:
	uv run pytest -m integration -q

test:
	uv run pytest -m "not e2e" -q --cov
	opa test --ignore fixtures policies/ --coverage
	pnpm --filter @ar/web test

test-e2e:
	pnpm --filter @ar/web exec playwright test

check: lint typecheck test-unit

gen:
	uv run python scripts/gen_openapi.py
	uv run python scripts/gen_json_schema.py
	uv run python scripts/sync_agent_docs.py
	pnpm --filter @ar/api-client gen
	uv run python scripts/strip_generated_markers.py
	uv run python scripts/gen_python_client.py
	pnpm exec biome format --write openapi.json

eval:
	@echo "not available until M8-T01"; exit 0

reset-db:
	$(COMPOSE) --profile deps exec -T postgres dropdb -U ar_owner --if-exists agentic_runtime
	$(COMPOSE) --profile deps exec -T postgres createdb -U ar_owner agentic_runtime
	$(MAKE) migrate seed

kind-up:
	@echo "not available until M15-T01"; exit 0

kind-down:
	@echo "not available until M15-T01"; exit 0

images:
	./scripts/build_images.sh

images-bundle:
	@echo "not available until M15-T04"; exit 0
