# ADR-0020: UUIDv7 ids, signed cursor pagination, RFC 9457 errors

- Status: Accepted
- Date: 2026-10-20

## Context

APIs need sortable ids, stable pagination over changing data and machine-readable errors.

## Decision

UUIDv7 (Postgres 18 `uuidv7()`) for all ids; cursor pagination with HMAC-signed opaque cursors (`AR_CURSOR_SECRET`); errors as `application/problem+json` with a stable `code` catalogue ([api-conventions](../../05-contracts/api-conventions.md)).

## Consequences

Index-friendly ids, tamper-proof cursors, consistent error handling in clients. Cost: no offset pagination (by design).

## Alternatives considered

Integer ids (rejected: enumeration, multi-region merges); offset pagination (rejected: inconsistent under writes).
