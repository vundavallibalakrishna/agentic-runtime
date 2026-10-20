# ADR-0001: Modular monolith with several deployables

- Status: Accepted
- Date: 2026-10-20

## Context

The product has ~20 domain modules (agents, runs, tools, policy, knowledge, …) that share one transactional data model (runs reference agent versions, tool calls reference approvals, everything is tenant-scoped). The team building it is small and largely AI coding agents working task by task.

## Decision

Build a **modular monolith**: one Python domain library `ar_domain` with explicit module boundaries (each module owns its tables, exposes a `service` API, and other modules may only import `ar_domain.<module>.service` and `ar_domain.<module>.schemas`), hosted by thin deployables (`api`, `runtime-worker`, `system-worker`, `ingest-worker`, `model-gateway`, `mcp-gateway`, `sandbox-manager`, `channels`). One Postgres database and one Alembic history. Boundaries are enforced with `import-linter` contracts in CI.

## Consequences

Simple local development and transactions (outbox in the same transaction as state changes); deployables scale independently where the load profile differs (runtime vs ingest vs gateways); extracting a module into a separate service later only requires replacing its `service` facade with a client. Risk: boundary erosion, mitigated by import-linter and module-owned tables ([service-decomposition](../service-decomposition.md)).

## Alternatives considered

Microservices per module (rejected: distributed transactions, 15+ databases, high operational load for single-tenant installs); single deployable (rejected: sandbox/gateway/ingest workloads need separate scaling and network policies).
