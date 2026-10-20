# Row-level security (tenancy enforcement in Postgres)

RLS is **defence in depth**. The primary control is that every repository function takes a `TenantContext` and filters by `tenant_id`; RLS guarantees that a missing filter cannot leak data across tenants. See [tenancy-isolation](../02-architecture/tenancy-isolation.md).

## 1. Database roles

| Role | Login | Used by | Privileges |
|---|---|---|---|
| `ar_owner` | yes (migrations only) | `migrate` job | Owns all objects. `BYPASSRLS`. Never used by running services. |
| `ar_app` | yes | `api`, all workers, `model-gateway`, `mcp-gateway`, `sandbox-manager` | `SELECT, INSERT, UPDATE, DELETE` on all tables except: `audit_events` (`SELECT, INSERT` only). **Not** owner, **no** `BYPASSRLS`. |
| `ar_platform` | yes | platform-admin code paths (tenant provisioning, cross-tenant usage reports, outbox relay, reapers) | Same grants as `ar_app` plus `BYPASSRLS`. Used only through `ar_domain.db.platform_session()`, which writes an audit event `platform.session_opened` with the reason. |
| `ar_readonly` | yes | BI / support break-glass | `SELECT` on all tables, subject to RLS. |

`ALTER TABLE ... FORCE ROW LEVEL SECURITY` is set on every tenant table so even the owner is subject to policies outside migrations.

## 2. Session variables

Every transaction opened by `ar_domain.db.tenant_session(ctx)` runs, as its first statement:

```sql
SELECT set_config('app.tenant_id', :tenant_id, true),     -- true = local to transaction
       set_config('app.user_id', :user_id_or_empty, true),
       set_config('app.request_id', :request_id, true);
```

PgBouncer runs in **transaction** pooling mode; because the settings are transaction-local (`is_local = true`), they cannot leak between pooled clients. Code must never call `set_config(..., false)`.

If `app.tenant_id` is unset, `app_tenant_id()` returns NULL and every tenant policy evaluates to false: queries return zero rows and inserts fail. This is the desired fail-closed behaviour.

## 3. Policy templates

### 3.1 Tenant-owned tables (`tenant_id NOT NULL`)

Applied to every table in [schema.md](schema.md) with `tenant_id NOT NULL`:

```sql
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {t}
  USING (tenant_id = app_tenant_id())
  WITH CHECK (tenant_id = app_tenant_id());
```

### 3.2 Platform-or-own tables (`tenant_id` nullable)

`model_providers`, `models`, `model_aliases`, `tool_servers`, `tool_server_versions`, `tools`, `tool_versions`, `sandbox_templates`, `roles`:

```sql
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY read_platform_or_own ON {t} FOR SELECT
  USING (tenant_id IS NULL OR tenant_id = app_tenant_id());
CREATE POLICY write_own ON {t} FOR ALL
  USING (tenant_id = app_tenant_id())
  WITH CHECK (tenant_id = app_tenant_id());
```

Platform rows (`tenant_id IS NULL`) can only be written through `platform_session()`.

### 3.3 `audit_events` and `outbox_events`

`tenant_id` is nullable for platform events.

```sql
CREATE POLICY tenant_read ON audit_events FOR SELECT USING (tenant_id = app_tenant_id());
CREATE POLICY tenant_insert ON audit_events FOR INSERT WITH CHECK (tenant_id = app_tenant_id());
-- outbox_events: same two policies; platform-level rows are written/read via platform_session().
```

### 3.4 Global tables

`plans`, `tenants`: RLS enabled with

```sql
CREATE POLICY read_all ON plans FOR SELECT USING (true);
CREATE POLICY read_own ON tenants FOR SELECT USING (id = app_tenant_id());
```

Writes only via `platform_session()`. Tenant lookup by slug or Keycloak organization during login uses `platform_session()` (read-only query `identity.repository.find_tenant_for_login`).

## 4. Non-tenant lookups that must work before a tenant is known

| Lookup | Function | Session |
|---|---|---|
| Resolve tenant from Keycloak `organization` claim at login | `identity.repository.find_tenant_for_login(org_id)` | platform (read-only) |
| API key authentication (`ark_` prefix → tenant) | `identity.repository.find_api_key_by_prefix(prefix)` | platform (read-only), then switch to tenant session |
| SCIM token authentication | `identity.repository.find_scim_token_by_prefix` | platform (read-only) |
| Inbound routine webhook by `webhook_path_token` | `routines.repository.find_by_webhook_token` | platform (read-only) |
| Slack/Teams event → integration by team/app id | `channels.repository.find_integration_by_external_id` | platform (read-only) |
| Platform admin switching into a tenant: active support grant | `identity.repository.find_active_support_grant(tenant_id, operator_subject)` | platform (read-only) |

These functions select only the minimum columns needed to establish the tenant, then the request continues in a tenant session.

## 5. Tests (mandatory)

See [testing-strategy](../08-quality/testing-strategy.md).

- `test_rls_every_tenant_table_has_policy`: queries `pg_class`/`pg_policies` and fails if any table with a `tenant_id` column lacks `relrowsecurity AND relforcerowsecurity` and a policy.
- `test_rls_cross_tenant_read_returns_nothing`: for each tenant table, insert a row for tenant A via owner, query as `ar_app` with tenant B context, expect zero rows.
- `test_rls_insert_wrong_tenant_rejected`: insert with mismatched tenant id raises `new row violates row-level security policy`.
- `test_rls_no_context_fails_closed`: query without `app.tenant_id` returns zero rows.
- `test_audit_append_only`: UPDATE/DELETE on `audit_events` raises.

## 6. Dedicated database tier

Tenants with `isolation_tier = 'dedicated_db'` get their own Postgres database (same schema, same migrations). `ar_domain.db.engine_for(tenant)` routes by tenant via the `AR_TENANT_DB_ROUTES` setting (JSON map `tenant_id → DSN secret path`). RLS remains enabled. `dedicated_cluster` is a separate install of the whole platform in single-tenant mode ([deployment-modes](../00-overview/deployment-modes.md)).
