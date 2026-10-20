# ADR-0017: FastAPI-generated OpenAPI as the contract; generated TS and Python clients

- Status: Accepted
- Date: 2026-10-20

## Context

Web, SDKs and tests must match the API precisely.

## Decision

Pydantic models in `ar_contracts` are the source of truth; `make gen` exports OpenAPI 3.1 from `api`, generates `@ar/api-client` (hey-api) and `ar_client` (openapi-python-client), and JSON Schemas for definitions and stream events. CI fails if generated files differ (`git diff --exit-code`).

## Consequences

No hand-written client drift. Cost: codegen step in the dev loop.

## Alternatives considered

Hand-written clients (rejected); GraphQL (rejected: streaming and caching semantics simpler with REST + SSE).
