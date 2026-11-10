# ADR-0033: Postgres is the read model

- Status: Accepted
- Date: 2026-11-10

## Context

API requests are served from the in-memory `ChatService`, with write-behind to Postgres. That store is process-local, so a second API replica does not see the first replica's turns, and a restart depends on what happened to be flushed.

## Decision

Postgres is the read model for API requests. The in-memory `ChatService` becomes a test double. It is retired from the production path in Stage 8.

Run events are written in the same transaction as the change they describe. Repositories run per request, with the tenant context set. Stage 8 is the last stage, and it records the single Alembic head.

## Consequences

Any API replica can read a conversation after the commit. Tests that need a process-local store construct the double themselves. Production composition does not.

## Alternatives

Keep `ChatService` as a cache in front of Postgres. Rejected: a cache that can answer a write the database has not committed is a second read model. Make the memory store the source of truth and replicate it. Rejected: Postgres and row-level security are already that store.
