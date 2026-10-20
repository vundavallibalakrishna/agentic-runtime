# ADR-0008: Shared-schema multi-tenancy with Postgres RLS; dedicated DB option

- Status: Accepted
- Date: 2026-10-20

## Context

SaaS needs strict isolation at reasonable cost; enterprise single-tenant installs need the same code.

## Decision

Every tenant-owned table has `tenant_id` and an RLS policy using `app_tenant_id()` from the transaction-local setting `app.tenant_id`; application connects as `ar_app` (no BYPASSRLS). Platform jobs use `ar_platform` explicitly. Tenants with `isolation_tier='dedicated_db'` are routed to their own database via `AR_TENANT_DB_ROUTES` ([rls.md](../../04-data/rls.md), [tenancy-isolation](../tenancy-isolation.md)).

## Consequences

Defence in depth against missing `WHERE tenant_id` bugs; one schema to migrate. Cost: RLS-aware testing and careful use of pre-tenant lookup functions.

## Alternatives considered

Schema-per-tenant (rejected: migration fan-out, catalog bloat at thousands of tenants); DB-per-tenant only (rejected: cost for small tenants).
