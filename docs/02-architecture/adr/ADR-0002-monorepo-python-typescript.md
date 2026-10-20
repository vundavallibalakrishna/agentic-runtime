# ADR-0002: Monorepo with uv (Python) and pnpm + Turborepo (TypeScript)

- Status: Accepted
- Date: 2026-10-20

## Context

Backend is Python (FastAPI, Temporal, MCP SDK); frontend is Next.js. Contracts (OpenAPI, stream events, definition schemas) must stay in sync between them.

## Decision

One Git monorepo: `uv` workspace for Python packages (`services/*`, `libs/*`, `connectors/*`), `pnpm` workspace + Turborepo for TypeScript (`apps/web`, `packages/*`). A root `Makefile` is the single entry point (`make dev`, `make test`, `make gen`, `make lint`). Versions pinned in [stack.md](../../stack.md).

## Consequences

Atomic changes across API and UI; generated client always matches the server; one CI pipeline with path filters. Cost: two toolchains in CI images.

## Alternatives considered

Polyrepo (rejected: contract drift); Nx (rejected: Turborepo is sufficient and simpler).
