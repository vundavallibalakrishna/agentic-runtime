# Database schema (authoritative DDL)

This is the **single source of truth** for tables, columns, types, constraints and indexes. SQLAlchemy models in `libs/ar_domain/src/ar_domain/<module>/models.py` must match this DDL exactly; Alembic migrations create it. Related: [ER diagram](er-diagram.md), [RLS](rls.md), [migrations](migrations.md).

## 0. Conventions

- PostgreSQL 18. Extensions: `vector` (pgvector 0.8.7), `pg_trgm`, `citext`, `btree_gin`.
- Primary keys: `id uuid PRIMARY KEY DEFAULT uuidv7()` (the application also generates UUIDv7 via `ar_common.ids.new_id()` so ids are known before insert).
- Every tenant-owned table has `tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`, an index whose leading column is `tenant_id`, and RLS enabled + forced ([rls.md](rls.md)). Tables marked **(global)** have no tenant RLS. Tables with a nullable `tenant_id` (platform-provided rows) use the "platform-or-own" RLS policy.
- Timestamps are `timestamptz`. `created_at DEFAULT now()`, `updated_at DEFAULT now()` maintained by trigger `set_updated_at()`.
- Enumerations are `text` with a `CHECK` constraint (not Postgres enum types) so adding a value is a cheap migration.
- Money/cost is stored as integer **micro-units** of the tenant billing currency (`cost_micros bigint`, 1 unit = 1,000,000 micros).
- Soft delete only where a `deleted_at` column exists; otherwise hard delete with FK cascades.
- JSONB columns are validated by the Pydantic model named in the comment (`-- schema: ar_contracts.X`).
- Embedding dimension for pgvector columns is the platform constant `AR_PGVECTOR_DIMENSIONS = 1024` ([ADR-0009](../02-architecture/adr/ADR-0009-retrieval-stores.md)).
- The zero UUID `00000000-0000-0000-0000-000000000000` is used only as a sentinel in unique indexes and rollup keys.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gin;

CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END $$;

-- helper used by RLS policies (see rls.md)
CREATE FUNCTION app_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$;
```

## 1. Identity and tenancy (`ar_domain.identity`)

```sql
CREATE TABLE plans (                                   -- (global)
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  key           text NOT NULL UNIQUE,                  -- 'free','team','enterprise','self_hosted'
  name          text NOT NULL,
  limits        jsonb NOT NULL DEFAULT '{}',           -- schema: ar_contracts.tenants.PlanLimits
  is_public     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tenants (                                 -- (global; see rls.md for read rules)
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  slug               citext NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$'),
  name               text NOT NULL,
  status             text NOT NULL DEFAULT 'active' CHECK (status IN ('provisioning','active','suspended','deleting','deleted')),
  plan_id            uuid NOT NULL REFERENCES plans(id),
  keycloak_org_id    text UNIQUE,                      -- Keycloak Organization id
  isolation_tier     text NOT NULL DEFAULT 'shared' CHECK (isolation_tier IN ('shared','dedicated_db','dedicated_cluster')),
  data_residency     text NOT NULL DEFAULT 'in',       -- region tag
  billing_currency   char(3) NOT NULL DEFAULT 'INR',
  settings           jsonb NOT NULL DEFAULT '{}',      -- schema: ar_contracts.tenants.TenantSettings
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  deleted_at         timestamptz
);

CREATE TABLE tenant_domains (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  domain             citext NOT NULL UNIQUE,
  verification_token text NOT NULL,
  verified_at        timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_tenant_domains_tenant ON tenant_domains(tenant_id);

CREATE TABLE identity_providers (
  id             uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  kind           text NOT NULL CHECK (kind IN ('oidc','saml')),
  display_name   text NOT NULL,
  keycloak_alias text NOT NULL UNIQUE,                 -- alias of the brokered IdP in Keycloak
  config         jsonb NOT NULL,                       -- schema: ar_contracts.identity.IdpConfig (no secrets)
  secret_ref_id  uuid,                                 -- FK added in section 2
  status         text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_identity_providers_tenant ON identity_providers(tenant_id);

CREATE TABLE users (
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  idp_subject      text NOT NULL,                      -- Keycloak user id (sub)
  email            citext NOT NULL,
  display_name     text NOT NULL,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('invited','active','suspended','deprovisioned')),
  attributes       jsonb NOT NULL DEFAULT '{}',        -- ABAC: department, location, clearance, employee_type
  settings         jsonb NOT NULL DEFAULT '{}',        -- schema: ar_contracts.identity.UserSettings
  scim_external_id text,
  last_login_at    timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idp_subject),
  UNIQUE (tenant_id, email)
);
CREATE INDEX ix_users_tenant_status ON users(tenant_id, status);

CREATE TABLE groups (
  id           uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name         text NOT NULL,
  source       text NOT NULL CHECK (source IN ('scim','idp_claim','local')),
  external_id  text,                                   -- SCIM id or IdP group id
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name),
  UNIQUE (tenant_id, external_id)
);

CREATE TABLE group_members (
  tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  group_id   uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (group_id, user_id)
);
CREATE INDEX ix_group_members_user ON group_members(tenant_id, user_id);

CREATE TABLE teams (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  slug        citext NOT NULL,
  name        text NOT NULL,
  description text NOT NULL DEFAULT '',
  group_id    uuid REFERENCES groups(id) ON DELETE SET NULL,  -- optional: membership mirrored from an IdP group
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE team_members (
  tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  team_id    uuid NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  team_role  text NOT NULL DEFAULT 'member' CHECK (team_role IN ('member','lead')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (team_id, user_id)
);
CREATE INDEX ix_team_members_user ON team_members(tenant_id, user_id);

CREATE TABLE roles (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid REFERENCES tenants(id) ON DELETE CASCADE,  -- NULL = system role (seeded)
  key         text NOT NULL CHECK (key ~ '^[a-z][a-z0-9_]{1,40}$'),
  name        text NOT NULL,
  description text NOT NULL DEFAULT '',
  permissions text[] NOT NULL,                                -- docs/06-security/authn-authz.md
  is_system   boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_roles_key ON roles (coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), key);

CREATE TABLE service_accounts (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name        text NOT NULL,
  description text NOT NULL DEFAULT '',
  status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  allow_on_behalf_of boolean NOT NULL DEFAULT false,  -- may start runs on behalf of tenant users (POST /api/v1/runs on_behalf_of_user_id)
  created_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE role_assignments (
  id             uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  role_id        uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  principal_type text NOT NULL CHECK (principal_type IN ('user','group','team','service_account')),
  principal_id   uuid NOT NULL,
  scope_type     text NOT NULL DEFAULT 'tenant' CHECK (scope_type IN ('tenant','team')),
  scope_id       uuid,                                 -- team id when scope_type='team'
  created_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (tenant_id, role_id, principal_type, principal_id, scope_type, scope_id),
  CHECK ((scope_type = 'tenant' AND scope_id IS NULL) OR (scope_type = 'team' AND scope_id IS NOT NULL))
);
CREATE INDEX ix_role_assignments_principal ON role_assignments(tenant_id, principal_type, principal_id);

CREATE TABLE api_keys (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  service_account_id uuid REFERENCES service_accounts(id) ON DELETE CASCADE,
  user_id            uuid REFERENCES users(id) ON DELETE CASCADE,       -- personal access key
  name               text NOT NULL,
  prefix             text NOT NULL UNIQUE,              -- 12 chars after 'ark_' (shown in UI, used for lookup)
  secret_hash        text NOT NULL,                     -- SHA-256 hex of the full key
  scopes             text[] NOT NULL DEFAULT '{}',      -- subset of permissions; empty = all permissions of the principal
  expires_at         timestamptz,
  last_used_at       timestamptz,
  revoked_at         timestamptz,
  created_by         uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  CHECK ((service_account_id IS NULL) <> (user_id IS NULL))
);
CREATE INDEX ix_api_keys_tenant ON api_keys(tenant_id);

CREATE TABLE scim_tokens (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  prefix      text NOT NULL UNIQUE,
  secret_hash text NOT NULL,
  expires_at  timestamptz,
  revoked_at  timestamptz,
  created_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_scim_tokens_tenant ON scim_tokens(tenant_id);

CREATE TABLE invitations (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email       citext NOT NULL,
  role_keys   text[] NOT NULL DEFAULT '{member}',
  token_hash  text NOT NULL UNIQUE,
  invited_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  expires_at  timestamptz NOT NULL,
  accepted_at timestamptz,
  revoked_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_invitations_tenant_email ON invitations(tenant_id, email);

CREATE TABLE support_access_grants (                -- SaaS only: time-boxed operator access to tenant data
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  operator_subject text NOT NULL,                    -- Keycloak subject of the platform admin
  operator_email   citext NOT NULL,
  level            text NOT NULL CHECK (level IN ('metadata','content')),
  reason           text NOT NULL CHECK (length(reason) BETWEEN 10 AND 1000),
  ticket_ref       text NOT NULL DEFAULT '',
  granted_by       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at       timestamptz NOT NULL,             -- ≤ granted + 72 h
  revoked_at       timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_support_grants_active ON support_access_grants(tenant_id, operator_subject) WHERE revoked_at IS NULL;
```

Note on `api_keys.secret_hash`: keys are 32 random bytes (base62), so SHA-256 is sufficient and lookup is by `prefix` with constant-time compare. The platform never stores passwords (Keycloak owns credentials).

## 2. Secrets and credentials (`ar_domain.secrets`)

```sql
CREATE TABLE secret_refs (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name        text NOT NULL,
  kind        text NOT NULL CHECK (kind IN ('api_key','basic_auth','bearer_token','oauth_client','oauth_refresh_token','db_dsn','webhook_secret','generic')),
  backend     text NOT NULL CHECK (backend IN ('vault','db_encrypted')),
  path        text NOT NULL,                          -- vault: 'ar/tenants/{tenant_id}/secrets/{id}'; db_encrypted: encrypted_secrets.id
  version     int NOT NULL DEFAULT 1,
  description text NOT NULL DEFAULT '',
  owner_user_id uuid REFERENCES users(id) ON DELETE CASCADE,  -- set for personal secrets (credential grants)
  created_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  rotated_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (tenant_id, owner_user_id, name)   -- personal secrets (e.g. '__delegation__') are unique per user
);

CREATE TABLE encrypted_secrets (                     -- only used when AR_SECRETS_BACKEND=db_encrypted
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key_id      text NOT NULL,                          -- KEK id from AR_DB_ENCRYPTION_KEYS
  wrapped_dek bytea NOT NULL,                         -- data key encrypted with KEK (AES-256-GCM)
  nonce       bytea NOT NULL,
  ciphertext  bytea NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_encrypted_secrets_tenant ON encrypted_secrets(tenant_id);

ALTER TABLE identity_providers ADD CONSTRAINT fk_idp_secret FOREIGN KEY (secret_ref_id) REFERENCES secret_refs(id) ON DELETE SET NULL;

CREATE TABLE credential_providers (
  id                      uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id               uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  slug                    citext NOT NULL,
  name                    text NOT NULL,
  kind                    text NOT NULL CHECK (kind IN ('oauth2','api_key','token_exchange')),
  authorize_url           text,
  token_url               text,
  client_id               text,
  client_secret_ref_id    uuid REFERENCES secret_refs(id) ON DELETE RESTRICT,
  default_scopes          text[] NOT NULL DEFAULT '{}',
  token_exchange_audience text,                       -- kind='token_exchange' (RFC 8693 via Keycloak)
  extra                   jsonb NOT NULL DEFAULT '{}',
  status                  text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE credential_grants (
  id                     uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id              uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id                uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider_id            uuid NOT NULL REFERENCES credential_providers(id) ON DELETE CASCADE,
  scopes                 text[] NOT NULL DEFAULT '{}',
  secret_ref_id          uuid NOT NULL REFERENCES secret_refs(id) ON DELETE CASCADE,  -- refresh token / api key
  status                 text NOT NULL DEFAULT 'active' CHECK (status IN ('active','expired','revoked','error')),
  external_account_label text,
  expires_at             timestamptz,
  last_used_at           timestamptz,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, user_id, provider_id)
);
```

## 3. Models (`ar_domain.models`)

```sql
CREATE TABLE model_providers (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id       uuid REFERENCES tenants(id) ON DELETE CASCADE,  -- NULL = platform-provided
  name            text NOT NULL,
  kind            text NOT NULL CHECK (kind IN ('openai_compatible','vllm','tei','fake')),
  base_url        text NOT NULL,                      -- e.g. http://vllm-reasoning.inference.svc:8000/v1
  api_key_ref_id  uuid REFERENCES secret_refs(id) ON DELETE SET NULL,
  headers         jsonb NOT NULL DEFAULT '{}',        -- non-secret static headers
  timeout_s       int NOT NULL DEFAULT 120 CHECK (timeout_s BETWEEN 1 AND 900),
  max_concurrency int NOT NULL DEFAULT 64,
  status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  health          jsonb NOT NULL DEFAULT '{}',        -- {ok, latency_ms, checked_at, error}
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_model_providers_tenant ON model_providers(tenant_id);

CREATE TABLE models (
  id                           uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id                    uuid REFERENCES tenants(id) ON DELETE CASCADE,  -- NULL = platform-provided
  provider_id                  uuid NOT NULL REFERENCES model_providers(id) ON DELETE CASCADE,
  name                         text NOT NULL,
  upstream_model               text NOT NULL,         -- id sent upstream
  kind                         text NOT NULL CHECK (kind IN ('chat','embedding','rerank')),
  capabilities                 text[] NOT NULL DEFAULT '{}',  -- 'tools','vision','json_schema','reasoning','streaming'
  context_window               int,
  max_output_tokens            int,
  embedding_dimensions         int,
  price_input_micros_per_mtok  bigint NOT NULL DEFAULT 0,
  price_output_micros_per_mtok bigint NOT NULL DEFAULT 0,
  licence                      text NOT NULL DEFAULT '',
  status                       text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','deprecated')),
  created_at                   timestamptz NOT NULL DEFAULT now(),
  updated_at                   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_models_tenant ON models(tenant_id);

CREATE TABLE model_aliases (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid REFERENCES tenants(id) ON DELETE CASCADE,   -- NULL = platform default alias
  alias              text NOT NULL CHECK (alias ~ '^[a-z][a-z0-9_-]{1,40}$'),
  kind               text NOT NULL CHECK (kind IN ('chat','embedding','rerank')),
  primary_model_id   uuid NOT NULL REFERENCES models(id) ON DELETE RESTRICT,
  fallback_model_ids uuid[] NOT NULL DEFAULT '{}',
  traffic_split      jsonb NOT NULL DEFAULT '{}',     -- canary: {"<model_id>": 10}
  default_params     jsonb NOT NULL DEFAULT '{}',     -- temperature, top_p, max_tokens, reasoning_effort
  status             text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_model_aliases ON model_aliases (coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), alias);
```

Resolution rule: a tenant alias overrides a platform alias with the same name. Standard aliases: `reasoning`, `fast`, `vision`, `embed`, `rerank`.

## 4. Agents (`ar_domain.agents`)

```sql
CREATE TABLE agents (
  id                   uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  slug                 citext NOT NULL CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
  name                 text NOT NULL,
  description          text NOT NULL DEFAULT '',
  avatar_file_id       uuid,                          -- FK added in section 11
  owner_user_id        uuid REFERENCES users(id) ON DELETE SET NULL,
  owner_team_id        uuid REFERENCES teams(id) ON DELETE SET NULL,
  visibility           text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','team','tenant')),
  status               text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
  disabled_at          timestamptz,                   -- kill switch
  disabled_reason      text,
  risk_tier            text NOT NULL DEFAULT 'low' CHECK (risk_tier IN ('low','medium','high')),
  draft_version_id     uuid,
  published_version_id uuid,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);
CREATE INDEX ix_agents_tenant_status ON agents(tenant_id, status);

CREATE TABLE agent_versions (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  agent_id        uuid NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  version         int NOT NULL,
  state           text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft','published','superseded')),
  definition      jsonb NOT NULL,                     -- schema: ar_contracts.definitions.AgentDefinition
  definition_hash text NOT NULL,                      -- sha256 hex of JCS(definition)
  change_note     text NOT NULL DEFAULT '',
  created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  published_at    timestamptz,
  published_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  UNIQUE (agent_id, version)
);
CREATE INDEX ix_agent_versions_tenant ON agent_versions(tenant_id, agent_id);
ALTER TABLE agents ADD CONSTRAINT fk_agents_draft FOREIGN KEY (draft_version_id) REFERENCES agent_versions(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE agents ADD CONSTRAINT fk_agents_published FOREIGN KEY (published_version_id) REFERENCES agent_versions(id) DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE agent_version_bindings (               -- denormalised references from a definition ("where used", integrity)
  tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  agent_version_id uuid NOT NULL REFERENCES agent_versions(id) ON DELETE CASCADE,
  kind             text NOT NULL CHECK (kind IN ('tool','tool_server','knowledge_collection','skill','subagent','sandbox_template','model_alias')),
  target_id        uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',  -- sentinel for model_alias
  target_key       text NOT NULL DEFAULT '',          -- alias name or version constraint, e.g. '^1'
  PRIMARY KEY (agent_version_id, kind, target_id, target_key)
);
CREATE INDEX ix_avb_target ON agent_version_bindings(tenant_id, kind, target_id);
```

Invariant: an agent version with `state='published'` is immutable (service layer + trigger `forbid_published_agent_version_update`). Editing a published agent creates a new draft version (`version = max + 1`).

## 5. Conversations, messages, runs (`ar_domain.conversations`, `ar_domain.runs`)

```sql
CREATE TABLE conversations (
  id                         uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id                  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id                    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,   -- owner (on-behalf-of identity)
  agent_id                   uuid NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
  agent_version_id           uuid REFERENCES agent_versions(id) ON DELETE SET NULL, -- pinned version (NULL = follow published)
  model_alias                text,                                   -- conversation override of the agent model alias
  channel                    text NOT NULL DEFAULT 'web' CHECK (channel IN ('web','slack','teams','email','api','routine','widget','eval')),
  title                      text NOT NULL DEFAULT '',
  status                     text NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
  pinned                     boolean NOT NULL DEFAULT false,
  is_preview                 boolean NOT NULL DEFAULT false,                         -- builder test chat on a draft version
  rolling_summary            text NOT NULL DEFAULT '',
  summary_through_message_id uuid,                    -- last message folded into rolling_summary
  plan                       jsonb NOT NULL DEFAULT '[]',  -- schema: ar_contracts.runs.PlanItem[]
  loaded_skills              jsonb NOT NULL DEFAULT '[]',  -- [{skill_id, version}] loaded via skills.load in this conversation
  retention_class            text NOT NULL DEFAULT 'standard' CHECK (retention_class IN ('standard','extended','legal_hold','ephemeral')),
  classification             text NOT NULL DEFAULT 'internal' CHECK (classification IN ('public','internal','confidential','restricted')),
  active_run_id              uuid,                    -- at most one non-terminal top-level run
  last_message_at            timestamptz,
  created_at                 timestamptz NOT NULL DEFAULT now(),
  updated_at                 timestamptz NOT NULL DEFAULT now(),
  deleted_at                 timestamptz
);
CREATE INDEX ix_conversations_user ON conversations(tenant_id, user_id, last_message_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX ix_conversations_agent ON conversations(tenant_id, agent_id);
CREATE INDEX ix_conversations_title_trgm ON conversations USING gin (title gin_trgm_ops);

CREATE TABLE conversation_shares (
  tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  principal_type  text NOT NULL CHECK (principal_type IN ('user','group','team')),
  principal_id    uuid NOT NULL,
  permission      text NOT NULL DEFAULT 'view' CHECK (permission IN ('view')),
  created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (conversation_id, principal_type, principal_id)
);

CREATE TABLE runs (
  id                   uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  conversation_id      uuid REFERENCES conversations(id) ON DELETE CASCADE,
  agent_id             uuid NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
  agent_version_id     uuid NOT NULL REFERENCES agent_versions(id) ON DELETE RESTRICT,
  parent_run_id        uuid REFERENCES runs(id) ON DELETE CASCADE,
  root_run_id          uuid NOT NULL,                 -- = id for top-level runs
  depth                int NOT NULL DEFAULT 0 CHECK (depth BETWEEN 0 AND 3),
  trigger              text NOT NULL CHECK (trigger IN ('chat','api','channel','routine','subagent','eval')),
  routine_id           uuid,                          -- FK added in section 13
  user_id              uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,   -- on-behalf-of identity
  initiator_type       text NOT NULL CHECK (initiator_type IN ('user','service_account','routine','system')),
  initiator_id         uuid,
  input_message_id     uuid,
  status               text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','waiting_approval','waiting_input','completed','failed','cancelled','budget_exceeded')),
  temporal_workflow_id text NOT NULL UNIQUE,          -- 'run-{id}'
  budget               jsonb NOT NULL,                -- schema: ar_contracts.runs.RunBudget
  callback_url         text,                          -- POST /api/v1/runs callback (https)
  notify_on_complete   boolean NOT NULL DEFAULT false,
  eval_context         jsonb,                         -- trigger='eval' only: {suite_id, case_id, tool_mocks, as_user, mock_all_tools}
  usage                jsonb NOT NULL DEFAULT '{}',   -- schema: ar_contracts.runs.RunUsage
  result_summary       text,                          -- final text (truncated to 8,000 chars)
  error                jsonb,                         -- {code, message, retriable}
  trace_id             text,
  last_event_seq       int NOT NULL DEFAULT 0,
  started_at           timestamptz,
  ended_at             timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_runs_conversation ON runs(tenant_id, conversation_id, created_at DESC);
CREATE INDEX ix_runs_active ON runs(tenant_id, status) WHERE status IN ('queued','running','waiting_approval','waiting_input');
CREATE INDEX ix_runs_parent ON runs(parent_run_id);
CREATE INDEX ix_runs_routine ON runs(tenant_id, routine_id, created_at DESC);
ALTER TABLE conversations ADD CONSTRAINT fk_conv_active_run FOREIGN KEY (active_run_id) REFERENCES runs(id) ON DELETE SET NULL;

CREATE TABLE messages (
  id                uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  conversation_id   uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  run_id            uuid REFERENCES runs(id) ON DELETE SET NULL,
  parent_message_id uuid REFERENCES messages(id) ON DELETE SET NULL,  -- branch parent (edit / regenerate)
  role              text NOT NULL CHECK (role IN ('user','assistant','tool','system')),
  content           jsonb NOT NULL,                   -- schema: ar_contracts.messages.ContentPart[]
  status            text NOT NULL DEFAULT 'completed' CHECK (status IN ('streaming','completed','failed','cancelled')),
  is_active_branch  boolean NOT NULL DEFAULT true,
  scope             text NOT NULL DEFAULT 'conversation' CHECK (scope IN ('conversation','run')),  -- 'run' = internal to a subagent run (hidden from the conversation view)
  model_alias       text,
  model_id          uuid REFERENCES models(id) ON DELETE SET NULL,
  tokens_in         int NOT NULL DEFAULT 0,
  tokens_out        int NOT NULL DEFAULT 0,
  author_user_id    uuid REFERENCES users(id) ON DELETE SET NULL,
  external_ref      text,                             -- Slack ts / Teams activity id / email Message-ID
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_messages_conversation ON messages(tenant_id, conversation_id, created_at);
CREATE INDEX ix_messages_run ON messages(run_id);
CREATE INDEX ix_messages_fts ON messages USING gin (to_tsvector('simple', content::text));
ALTER TABLE runs ADD CONSTRAINT fk_runs_input_msg FOREIGN KEY (input_message_id) REFERENCES messages(id) ON DELETE SET NULL;

CREATE TABLE message_feedback (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  message_id  uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rating      text NOT NULL CHECK (rating IN ('up','down')),
  reasons     text[] NOT NULL DEFAULT '{}',           -- 'incorrect','unhelpful','unsafe','slow','other'
  comment     text NOT NULL DEFAULT '',
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (message_id, user_id)
);

CREATE TABLE run_steps (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  run_id        uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  seq           int NOT NULL,
  kind          text NOT NULL CHECK (kind IN ('model_call','tool_batch','compaction','delegation','approval_wait','memory_recall','finalize')),
  status        text NOT NULL CHECK (status IN ('running','succeeded','failed','skipped','cancelled')),
  model_alias   text,
  model_id      uuid REFERENCES models(id) ON DELETE SET NULL,
  tokens_in     int NOT NULL DEFAULT 0,
  tokens_out    int NOT NULL DEFAULT 0,
  cached_tokens int NOT NULL DEFAULT 0,
  latency_ms    int,
  detail        jsonb NOT NULL DEFAULT '{}',          -- kind-specific, redacted
  started_at    timestamptz NOT NULL DEFAULT now(),
  ended_at      timestamptz,
  UNIQUE (run_id, seq)
);
CREATE INDEX ix_run_steps_tenant ON run_steps(tenant_id, run_id);

CREATE TABLE run_events (                           -- durable copy of the stream (replay, resume after Valkey expiry)
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  run_id      uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  seq         int NOT NULL,
  type        text NOT NULL,                          -- docs/05-contracts/stream-events.md
  data        jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, seq)
);
CREATE INDEX ix_run_events_tenant ON run_events(tenant_id, run_id);
```

`message.delta` and `reasoning.delta` events are **not** persisted to `run_events` (Valkey stream only); `message.completed` carries the full text, keeping `run_events` small.

## 6. Tools (`ar_domain.tools`)

```sql
CREATE TABLE data_connections (
  id                  uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name                text NOT NULL,
  engine              text NOT NULL CHECK (engine IN ('postgres','mysql','mssql','oracle','snowflake','trino','clickhouse')),
  dsn_secret_ref_id   uuid NOT NULL REFERENCES secret_refs(id) ON DELETE RESTRICT,
  identity_mode       text NOT NULL DEFAULT 'service' CHECK (identity_mode IN ('service','per_user_mapped','passthrough')),
  allowlist           jsonb NOT NULL DEFAULT '{}',    -- schema: ar_contracts.tools.SqlAllowlist {schemas, tables, columns_deny}
  row_limit           int NOT NULL DEFAULT 1000 CHECK (row_limit BETWEEN 1 AND 100000),
  statement_timeout_s int NOT NULL DEFAULT 30 CHECK (statement_timeout_s BETWEEN 1 AND 600),
  classification      text NOT NULL DEFAULT 'internal' CHECK (classification IN ('public','internal','confidential','restricted')),
  schema_notes        text NOT NULL DEFAULT '',       -- curated descriptions / glossary
  status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  created_by          uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE tool_servers (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid REFERENCES tenants(id) ON DELETE CASCADE,   -- NULL = platform built-in server
  slug               citext NOT NULL CHECK (slug ~ '^[a-z][a-z0-9_]{1,30}$'),
  name               text NOT NULL,
  description        text NOT NULL DEFAULT '',
  kind               text NOT NULL CHECK (kind IN ('remote_mcp','openapi','sql','builtin','sandbox')),
  owner_team_id      uuid REFERENCES teams(id) ON DELETE SET NULL,
  owner_user_id      uuid REFERENCES users(id) ON DELETE SET NULL,
  status             text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_review','approved','deprecated','rejected')),
  disabled_at        timestamptz,                     -- kill switch
  disabled_reason    text,
  current_version_id uuid,                            -- latest approved version
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_tool_servers_slug ON tool_servers (coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), slug);

CREATE TABLE tool_server_versions (
  id                     uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id              uuid REFERENCES tenants(id) ON DELETE CASCADE,
  tool_server_id         uuid NOT NULL REFERENCES tool_servers(id) ON DELETE CASCADE,
  version                text NOT NULL CHECK (version ~ '^\d+\.\d+\.\d+$'),
  endpoint_url           text,                        -- remote_mcp: https URL; openapi/sql: connector runtime URL (platform-set)
  config                 jsonb NOT NULL DEFAULT '{}', -- schema: ar_contracts.definitions.ToolServerConfig
  auth_mode              text NOT NULL DEFAULT 'none' CHECK (auth_mode IN ('none','static_secret','user_oauth','token_exchange','internal_jwt')),
  secret_ref_id          uuid REFERENCES secret_refs(id) ON DELETE RESTRICT,
  credential_provider_id uuid REFERENCES credential_providers(id) ON DELETE RESTRICT,
  manifest               jsonb NOT NULL DEFAULT '{}', -- snapshot of server/discover + tools/list
  manifest_hash          text NOT NULL DEFAULT '',
  review_status          text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
  review_notes           text NOT NULL DEFAULT '',
  reviewed_by            uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at            timestamptz,
  discovered_at          timestamptz,
  created_by             uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tool_server_id, version)
);
CREATE INDEX ix_tsv_tenant ON tool_server_versions(tenant_id, tool_server_id);
ALTER TABLE tool_servers ADD CONSTRAINT fk_ts_current FOREIGN KEY (current_version_id) REFERENCES tool_server_versions(id) DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE tools (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id       uuid REFERENCES tenants(id) ON DELETE CASCADE,  -- NULL for built-in tools
  tool_server_id  uuid NOT NULL REFERENCES tool_servers(id) ON DELETE CASCADE,
  name            text NOT NULL CHECK (name ~ '^[a-z][a-z0-9_]{0,47}$'),
  qualified_name  text NOT NULL,                      -- '{server_slug}.{name}', e.g. 'jira.create_issue'
  disabled_at     timestamptz,                        -- kill switch
  disabled_reason text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tool_server_id, name)
);
CREATE INDEX ix_tools_tenant ON tools(tenant_id);

CREATE TABLE tool_versions (
  id                     uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id              uuid REFERENCES tenants(id) ON DELETE CASCADE,
  tool_id                uuid NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
  tool_server_version_id uuid NOT NULL REFERENCES tool_server_versions(id) ON DELETE CASCADE,
  title                  text NOT NULL DEFAULT '',
  description            text NOT NULL,               -- reviewed text shown to the model
  description_hash       text NOT NULL,               -- sha256(description) for tool-poisoning detection
  input_schema           jsonb NOT NULL,              -- JSON Schema 2020-12
  output_schema          jsonb,
  annotations            jsonb NOT NULL DEFAULT '{}', -- MCP annotations (readOnlyHint, destructiveHint, idempotentHint, openWorldHint)
  risk_class             text NOT NULL CHECK (risk_class IN ('R0','R1','W1','W2','W3')),
  data_classification    text NOT NULL DEFAULT 'internal' CHECK (data_classification IN ('public','internal','confidential','restricted')),
  required_scopes        text[] NOT NULL DEFAULT '{}',
  timeout_s              int NOT NULL DEFAULT 60 CHECK (timeout_s BETWEEN 1 AND 900),
  rate_limit_per_minute  int NOT NULL DEFAULT 60,
  max_result_bytes       int NOT NULL DEFAULT 65536,
  idempotent             boolean NOT NULL DEFAULT false,
  approval_preview       jsonb NOT NULL DEFAULT '{}', -- schema: ar_contracts.tools.PreviewTemplate
  embedding              vector(1024),                -- tool search
  created_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tool_id, tool_server_version_id)
);
CREATE INDEX ix_tool_versions_tenant ON tool_versions(tenant_id, tool_id);
CREATE INDEX ix_tool_versions_embedding ON tool_versions USING hnsw (embedding vector_cosine_ops);

CREATE TABLE tool_calls (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  run_id             uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  run_step_id        uuid REFERENCES run_steps(id) ON DELETE SET NULL,
  message_id         uuid REFERENCES messages(id) ON DELETE SET NULL,  -- assistant message that requested it
  tool_id            uuid REFERENCES tools(id) ON DELETE SET NULL,
  tool_version_id    uuid REFERENCES tool_versions(id) ON DELETE SET NULL,
  qualified_name     text NOT NULL,
  model_call_id      text NOT NULL,                   -- id assigned by the model
  arguments_redacted jsonb NOT NULL,                  -- PII-redacted copy
  args_hash          text NOT NULL,                   -- sha256(JCS({tool_version_id, arguments}))
  risk_class         text NOT NULL,
  policy_decision    text CHECK (policy_decision IN ('allow','deny','require_approval')),
  policy_reasons     text[] NOT NULL DEFAULT '{}',
  approval_id        uuid,                            -- FK added in section 7
  status             text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','awaiting_approval','running','succeeded','failed','denied','rejected','expired','cancelled')),
  idempotency_key    text NOT NULL,                   -- '{run_id}:{model_call_id}'
  result_preview     text,                            -- truncated, redacted
  result_file_id     uuid,                            -- offloaded full result (files.kind='tool_result')
  is_error           boolean NOT NULL DEFAULT false,
  error              jsonb,
  latency_ms         int,
  started_at         timestamptz,
  ended_at           timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX ix_tool_calls_run ON tool_calls(tenant_id, run_id);
CREATE INDEX ix_tool_calls_tool ON tool_calls(tenant_id, tool_id, created_at DESC);
```

## 7. Policy and approvals (`ar_domain.policy`, `ar_domain.approvals`)

```sql
CREATE TABLE policies (
  id                uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name              text NOT NULL,
  description       text NOT NULL DEFAULT '',
  kind              text NOT NULL DEFAULT 'rules' CHECK (kind IN ('rules','rego')),
  status            text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','disabled')),
  priority          int NOT NULL DEFAULT 100,         -- ordering for display / reason reporting only
  active_version_id uuid,
  created_by        uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE policy_versions (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  policy_id   uuid NOT NULL REFERENCES policies(id) ON DELETE CASCADE,
  version     int NOT NULL,
  document    jsonb,                                  -- kind='rules': schema ar_contracts.definitions.PolicyDefinition
  rego        text,                                   -- kind='rego' (feature flag custom_rego)
  hash        text NOT NULL,
  test_report jsonb NOT NULL DEFAULT '{}',
  created_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (policy_id, version),
  CHECK ((document IS NOT NULL) <> (rego IS NOT NULL))
);
ALTER TABLE policies ADD CONSTRAINT fk_policies_active FOREIGN KEY (active_version_id) REFERENCES policy_versions(id) DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE approvals (
  id                    uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id             uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  tool_call_id          uuid NOT NULL UNIQUE REFERENCES tool_calls(id) ON DELETE CASCADE,
  run_id                uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  requested_for_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  agent_id              uuid NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  qualified_name        text NOT NULL,
  risk_class            text NOT NULL,
  status                text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','expired','cancelled')),
  args_hash             text NOT NULL,
  arguments             jsonb NOT NULL,               -- exact arguments (readable only by eligible approvers + auditors)
  preview               jsonb NOT NULL,               -- schema: ar_contracts.approvals.ApprovalPreview
  justification         text NOT NULL DEFAULT '',     -- model-provided reason (untrusted, labelled in UI)
  approver_rule         jsonb NOT NULL,               -- schema: ar_contracts.approvals.ApproverRule
  required_approvals    int NOT NULL DEFAULT 1 CHECK (required_approvals BETWEEN 1 AND 5),
  step_up_required      boolean NOT NULL DEFAULT false,
  policy_reasons        text[] NOT NULL DEFAULT '{}',
  expires_at            timestamptz NOT NULL,
  decided_at            timestamptz,
  consumed_at           timestamptz,                  -- set when the approved call executes (single use)
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_approvals_pending ON approvals(tenant_id, status, expires_at) WHERE status = 'pending';
CREATE INDEX ix_approvals_run ON approvals(run_id);
ALTER TABLE tool_calls ADD CONSTRAINT fk_tool_calls_approval FOREIGN KEY (approval_id) REFERENCES approvals(id) ON DELETE SET NULL;

CREATE TABLE approval_decisions (
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  approval_id      uuid NOT NULL REFERENCES approvals(id) ON DELETE CASCADE,
  approver_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  decision         text NOT NULL CHECK (decision IN ('approve','reject')),
  args_hash        text NOT NULL,                     -- hash the approver saw; must equal approvals.args_hash
  comment          text NOT NULL DEFAULT '',
  step_up_verified boolean NOT NULL DEFAULT false,
  channel          text NOT NULL CHECK (channel IN ('web','slack','teams','email','api')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (approval_id, approver_user_id)
);

CREATE TABLE standing_approvals (
  id                   uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  granted_by_user_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  agent_id             uuid REFERENCES agents(id) ON DELETE CASCADE,
  routine_id           uuid,                          -- FK added in section 13
  tool_id              uuid NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
  argument_constraints jsonb NOT NULL DEFAULT '[]',   -- schema: ar_contracts.approvals.ArgConstraint[]
  max_uses             int,
  uses                 int NOT NULL DEFAULT 0,
  expires_at           timestamptz NOT NULL,
  revoked_at           timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now(),
  CHECK (agent_id IS NOT NULL OR routine_id IS NOT NULL)
);
CREATE INDEX ix_standing_approvals_lookup ON standing_approvals(tenant_id, tool_id) WHERE revoked_at IS NULL;
```

## 8. Knowledge (`ar_domain.knowledge`)

```sql
CREATE TABLE knowledge_collections (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  slug               citext NOT NULL,
  name               text NOT NULL,
  description        text NOT NULL DEFAULT '',        -- shown to the model in knowledge.list_collections
  owner_team_id      uuid REFERENCES teams(id) ON DELETE SET NULL,
  visibility         text NOT NULL DEFAULT 'tenant' CHECK (visibility IN ('private','team','tenant')),
  acl_mode           text NOT NULL DEFAULT 'source' CHECK (acl_mode IN ('source','collection')),
  sensitivity        text NOT NULL DEFAULT 'normal' CHECK (sensitivity IN ('normal','high')),  -- high = late verification
  classification     text NOT NULL DEFAULT 'internal' CHECK (classification IN ('public','internal','confidential','restricted')),
  embedding_alias    text NOT NULL DEFAULT 'embed',
  embedding_model_id uuid REFERENCES models(id) ON DELETE SET NULL,
  index_version      int NOT NULL DEFAULT 1,
  store_backend      text NOT NULL DEFAULT 'pgvector' CHECK (store_backend IN ('pgvector','qdrant')),  -- RetrievalStore adapter (spec 10 §6)
  store_collection   text NOT NULL,                   -- adapter-specific physical target: 'pg:{dims}' or Qdrant collection name
  text_search_config text NOT NULL DEFAULT 'simple' CHECK (text_search_config IN ('simple','english')),  -- lexical signal (spec 10 §7.3)
  chunking           jsonb NOT NULL DEFAULT '{"target_tokens":512,"overlap_pct":12,"contextual":false}',
  stats              jsonb NOT NULL DEFAULT '{}',     -- {documents, chunks, bytes, failed}
  created_by         uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE knowledge_sources (
  id                   uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  collection_id        uuid NOT NULL REFERENCES knowledge_collections(id) ON DELETE CASCADE,
  name                 text NOT NULL,
  kind                 text NOT NULL CHECK (kind IN ('upload','web','s3','sharepoint','confluence','google_drive','database','mcp_resource')),
  config               jsonb NOT NULL DEFAULT '{}',   -- schema: ar_contracts.definitions.KnowledgeSourceConfig
  secret_ref_id        uuid REFERENCES secret_refs(id) ON DELETE RESTRICT,
  data_connection_id   uuid REFERENCES data_connections(id) ON DELETE RESTRICT,
  sync_schedule        text,                          -- cron in tenant timezone; NULL = manual/webhook
  acl_sync_schedule    text,                          -- cron; default '*/10 * * * *' for sources with ACLs
  temporal_schedule_id text,
  status               text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','error')),
  last_sync_at         timestamptz,
  last_sync_status     text,
  cursor               jsonb NOT NULL DEFAULT '{}',   -- delta token / watermark
  created_by           uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_knowledge_sources_collection ON knowledge_sources(tenant_id, collection_id);

CREATE TABLE documents (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  collection_id      uuid NOT NULL REFERENCES knowledge_collections(id) ON DELETE CASCADE,
  source_id          uuid NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
  external_id        text NOT NULL,
  uri                text NOT NULL,                   -- citation link
  title              text NOT NULL,
  mime_type          text NOT NULL,
  version_hash       text NOT NULL,                   -- sha256 of raw bytes
  size_bytes         bigint NOT NULL DEFAULT 0,
  language           text,
  classification     text NOT NULL DEFAULT 'internal' CHECK (classification IN ('public','internal','confidential','restricted')),
  acl_principals     text[] NOT NULL DEFAULT '{}',    -- 'user:{user_id}', 'group:{group_id}', 'tenant:*'
  acl_hash           text NOT NULL DEFAULT '',
  raw_file_id        uuid,
  parsed_file_id     uuid,
  summary            text NOT NULL DEFAULT '',
  status             text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','parsing','embedding','indexed','failed','deleted')),
  error              text,
  source_modified_at timestamptz,
  indexed_at         timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id)
);
CREATE INDEX ix_documents_collection ON documents(tenant_id, collection_id, status);
CREATE INDEX ix_documents_title_trgm ON documents USING gin (title gin_trgm_ops);

CREATE TABLE document_chunks (
  id             uuid PRIMARY KEY DEFAULT uuidv7(),  -- also chunk_embeddings.chunk_id / Qdrant point id
  tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  document_id    uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ordinal        int NOT NULL,
  text           text NOT NULL,
  context_prefix text NOT NULL DEFAULT '',
  heading_path   text[] NOT NULL DEFAULT '{}',
  page_from      int,
  page_to        int,
  token_count    int NOT NULL,
  index_version  int NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, ordinal, index_version)
);
CREATE INDEX ix_document_chunks_doc ON document_chunks(tenant_id, document_id);

-- pgvector RetrievalStore adapter (spec 10 §7). Empty when every collection uses store_backend = 'qdrant'.
CREATE TABLE chunk_embeddings (
  chunk_id           uuid PRIMARY KEY REFERENCES document_chunks(id) ON DELETE CASCADE,
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  collection_id      uuid NOT NULL REFERENCES knowledge_collections(id) ON DELETE CASCADE,
  document_id        uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  source_id          uuid NOT NULL,
  index_version      int NOT NULL,
  acl                text[] NOT NULL,                   -- copy of documents.acl_principals (updated by set_acl)
  classification     text NOT NULL CHECK (classification IN ('public','internal','confidential','restricted')),
  dims               smallint NOT NULL CHECK (dims IN (384,768,1024,1536,3072)),
  embedding          halfvec NOT NULL,                  -- length = dims (CHECK below)
  text_search_config regconfig NOT NULL DEFAULT 'simple',
  lexical_text       text NOT NULL,                     -- context_prefix + heading_path + text
  tsv                tsvector GENERATED ALWAYS AS (to_tsvector(text_search_config, lexical_text)) STORED,
  created_at         timestamptz NOT NULL DEFAULT now(),
  CHECK (vector_dims(embedding) = dims)
);
CREATE INDEX ix_chunk_emb_target ON chunk_embeddings(tenant_id, collection_id, index_version);
CREATE INDEX ix_chunk_emb_document ON chunk_embeddings(document_id);
CREATE INDEX ix_chunk_emb_acl ON chunk_embeddings USING gin (acl);
CREATE INDEX ix_chunk_emb_tsv ON chunk_embeddings USING gin (tsv);
-- one partial HNSW index per supported dimension d in (384,768,1024,1536,3072):
CREATE INDEX ix_chunk_emb_hnsw_1024 ON chunk_embeddings
  USING hnsw ((embedding::halfvec(1024)) halfvec_cosine_ops) WITH (m = 16, ef_construction = 64) WHERE dims = 1024;
-- ix_chunk_emb_hnsw_384, _768, _1536, _3072 identical with the dimension substituted.

CREATE TABLE ingestion_jobs (
  id                   uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  source_id            uuid REFERENCES knowledge_sources(id) ON DELETE CASCADE,
  collection_id        uuid NOT NULL REFERENCES knowledge_collections(id) ON DELETE CASCADE,
  kind                 text NOT NULL CHECK (kind IN ('full_sync','incremental_sync','acl_sync','reindex','single_document')),
  status               text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','partially_failed','failed','cancelled')),
  temporal_workflow_id text NOT NULL,
  stats                jsonb NOT NULL DEFAULT '{}',   -- {seen, added, updated, unchanged, deleted, failed}
  error                text,
  triggered_by         text NOT NULL CHECK (triggered_by IN ('schedule','manual','webhook','upload','system')),
  started_at           timestamptz,
  finished_at          timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ingestion_jobs_source ON ingestion_jobs(tenant_id, source_id, created_at DESC);
```

## 9. Memory (`ar_domain.memory`)

```sql
CREATE TABLE memory_facts (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  scope              text NOT NULL CHECK (scope IN ('user','agent','team','agent_user')),
  user_id            uuid REFERENCES users(id) ON DELETE CASCADE,
  agent_id           uuid REFERENCES agents(id) ON DELETE CASCADE,
  team_id            uuid REFERENCES teams(id) ON DELETE CASCADE,
  content            text NOT NULL CHECK (length(content) <= 1000),
  category           text NOT NULL DEFAULT 'fact' CHECK (category IN ('preference','fact','instruction','lesson','contact','glossary')),
  embedding          vector(1024),
  embedding_model_id uuid REFERENCES models(id) ON DELETE SET NULL,
  source_kind        text NOT NULL CHECK (source_kind IN ('explicit','extracted','tool_output','admin','import')),
  source_ref         jsonb NOT NULL DEFAULT '{}',     -- {conversation_id, message_id, run_id}
  trust_level        text NOT NULL DEFAULT 'high' CHECK (trust_level IN ('high','low')),
  confidence         real NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
  status             text NOT NULL DEFAULT 'active' CHECK (status IN ('active','pending_review','superseded','deleted')),
  superseded_by_id   uuid REFERENCES memory_facts(id) ON DELETE SET NULL,
  expires_at         timestamptz,
  last_recalled_at   timestamptz,
  recall_count       int NOT NULL DEFAULT 0,
  created_by         uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CHECK ( (scope = 'user' AND user_id IS NOT NULL)
       OR (scope = 'agent' AND agent_id IS NOT NULL)
       OR (scope = 'team' AND team_id IS NOT NULL)
       OR (scope = 'agent_user' AND agent_id IS NOT NULL AND user_id IS NOT NULL) )
);
CREATE INDEX ix_memory_user ON memory_facts(tenant_id, user_id) WHERE status = 'active';
CREATE INDEX ix_memory_agent ON memory_facts(tenant_id, agent_id) WHERE status = 'active';
CREATE INDEX ix_memory_team ON memory_facts(tenant_id, team_id) WHERE status = 'active';
CREATE INDEX ix_memory_embedding ON memory_facts USING hnsw (embedding vector_cosine_ops) WHERE status = 'active';
```

## 10. Sandboxes (`ar_domain.sandboxes`)

```sql
CREATE TABLE sandbox_templates (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid REFERENCES tenants(id) ON DELETE CASCADE,  -- NULL = platform template ('default','browser','data-science')
  slug               citext NOT NULL,
  name               text NOT NULL,
  image_ref          text NOT NULL,                   -- digest-pinned: registry/ar-sandbox@sha256:...
  runtime_class      text NOT NULL DEFAULT 'gvisor' CHECK (runtime_class IN ('gvisor','kata','runc_dev')),
  cpu_millis         int NOT NULL DEFAULT 2000,
  memory_mb          int NOT NULL DEFAULT 4096,
  disk_gb            int NOT NULL DEFAULT 10,
  allow_browser      boolean NOT NULL DEFAULT true,
  allow_packages     boolean NOT NULL DEFAULT false,  -- allow pip/npm installs through AR_SANDBOX_PACKAGE_MIRRORS
  egress_allowlist   text[] NOT NULL DEFAULT '{}',    -- domains; '*' rejected when AR_ENV=prod
  max_classification text NOT NULL DEFAULT 'confidential' CHECK (max_classification IN ('public','internal','confidential','restricted')),
  idle_suspend_s     int NOT NULL DEFAULT 900,
  max_lifetime_s     int NOT NULL DEFAULT 86400,
  exec_timeout_s     int NOT NULL DEFAULT 120,
  retention_days     int NOT NULL DEFAULT 7,
  status             text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_sandbox_templates_slug ON sandbox_templates (coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), slug);

CREATE TABLE sandboxes (
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  template_id      uuid NOT NULL REFERENCES sandbox_templates(id) ON DELETE RESTRICT,
  scope            text NOT NULL CHECK (scope IN ('conversation','agent_user','agent')),
  scope_key        text NOT NULL,                     -- 'conv:{id}' | 'au:{agent_id}:{user_id}' | 'agent:{id}'
  conversation_id  uuid REFERENCES conversations(id) ON DELETE SET NULL,
  agent_id         uuid REFERENCES agents(id) ON DELETE SET NULL,
  user_id          uuid REFERENCES users(id) ON DELETE SET NULL,
  status           text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','starting','ready','suspending','suspended','resuming','terminating','terminated','failed')),
  driver           text NOT NULL CHECK (driver IN ('docker','kubernetes')),
  driver_ref       text,                              -- pod name / container id
  endpoint_url     text,                              -- http://<ip>:8080/mcp
  auth_token_hash  text,                              -- sha256 of per-sandbox bearer token
  workspace_volume text,
  snapshot_file_id uuid,                              -- tar.zst of /workspace at suspend
  cpu_seconds      bigint NOT NULL DEFAULT 0,
  last_active_at   timestamptz NOT NULL DEFAULT now(),
  started_at       timestamptz,
  terminated_at    timestamptz,
  error            text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_sandboxes_live_scope ON sandboxes(tenant_id, scope_key) WHERE status NOT IN ('terminated','failed');
CREATE INDEX ix_sandboxes_idle ON sandboxes(status, last_active_at);
```

## 11. Files (`ar_domain.files`)

```sql
CREATE TABLE files (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  owner_user_id   uuid REFERENCES users(id) ON DELETE SET NULL,
  conversation_id uuid REFERENCES conversations(id) ON DELETE SET NULL,
  run_id          uuid REFERENCES runs(id) ON DELETE SET NULL,
  kind            text NOT NULL CHECK (kind IN ('upload','artifact','tool_result','sandbox_snapshot','knowledge_raw','knowledge_parsed','skill_asset','avatar','export','openapi_spec','eval_dataset','event_payload')),
  name            text NOT NULL,
  mime_type       text NOT NULL,
  size_bytes      bigint NOT NULL DEFAULT 0,
  sha256          text,
  object_key      text NOT NULL UNIQUE,               -- 't/{tenant_id}/{kind}/{yyyy}/{mm}/{id}'
  classification  text NOT NULL DEFAULT 'internal' CHECK (classification IN ('public','internal','confidential','restricted')),
  status          text NOT NULL DEFAULT 'pending_upload' CHECK (status IN ('pending_upload','ready','quarantined','deleted')),
  scan_status     text NOT NULL DEFAULT 'pending' CHECK (scan_status IN ('pending','clean','infected','skipped','error')),
  preview         jsonb NOT NULL DEFAULT '{}',        -- {page_count, width, height, text_excerpt, thumbnail_file_id}
  retention_until timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz
);
CREATE INDEX ix_files_owner ON files(tenant_id, owner_user_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX ix_files_conversation ON files(tenant_id, conversation_id);
CREATE INDEX ix_files_retention ON files(retention_until) WHERE deleted_at IS NULL;

ALTER TABLE agents ADD CONSTRAINT fk_agents_avatar FOREIGN KEY (avatar_file_id) REFERENCES files(id) ON DELETE SET NULL;
ALTER TABLE tool_calls ADD CONSTRAINT fk_tool_calls_result FOREIGN KEY (result_file_id) REFERENCES files(id) ON DELETE SET NULL;
ALTER TABLE documents ADD CONSTRAINT fk_documents_raw FOREIGN KEY (raw_file_id) REFERENCES files(id) ON DELETE SET NULL;
ALTER TABLE documents ADD CONSTRAINT fk_documents_parsed FOREIGN KEY (parsed_file_id) REFERENCES files(id) ON DELETE SET NULL;
ALTER TABLE sandboxes ADD CONSTRAINT fk_sandboxes_snapshot FOREIGN KEY (snapshot_file_id) REFERENCES files(id) ON DELETE SET NULL;
```

## 12. Skills (`ar_domain.skills`)

```sql
CREATE TABLE skills (
  id                   uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  slug                 citext NOT NULL CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
  name                 text NOT NULL,
  description          text NOT NULL CHECK (length(description) <= 500),  -- shown to the model to decide when to load
  owner_user_id        uuid REFERENCES users(id) ON DELETE SET NULL,
  owner_team_id        uuid REFERENCES teams(id) ON DELETE SET NULL,
  visibility           text NOT NULL DEFAULT 'tenant' CHECK (visibility IN ('private','team','tenant')),
  status               text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
  published_version_id uuid,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE skill_versions (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  skill_id        uuid NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  version         int NOT NULL CHECK (version >= 0),   -- 0 = mutable draft working copy
  instructions_md text NOT NULL CHECK (length(instructions_md) <= 50000),
  assets          jsonb NOT NULL DEFAULT '[]',        -- [{path, file_id, sha256}] mounted at /workspace/.skills/{slug}/
  required_tools  text[] NOT NULL DEFAULT '{}',       -- qualified names
  hash            text NOT NULL,
  created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (skill_id, version)
);
ALTER TABLE skills ADD CONSTRAINT fk_skills_published FOREIGN KEY (published_version_id) REFERENCES skill_versions(id) DEFERRABLE INITIALLY DEFERRED;
```

## 13. Routines (`ar_domain.routines`)

```sql
CREATE TABLE routines (
  id                    uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id             uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name                  text NOT NULL,
  description           text NOT NULL DEFAULT '',
  owner_user_id         uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  run_as                text NOT NULL DEFAULT 'owner' CHECK (run_as IN ('owner','service_account')),
  service_account_id    uuid REFERENCES service_accounts(id) ON DELETE RESTRICT,
  agent_id              uuid NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
  agent_version_id      uuid REFERENCES agent_versions(id) ON DELETE SET NULL,   -- NULL = published
  instructions          text NOT NULL CHECK (length(instructions) <= 20000),
  trigger_type          text NOT NULL CHECK (trigger_type IN ('schedule','webhook','channel_event','email','file_arrival','db_change','manual')),
  trigger_config        jsonb NOT NULL,              -- schema: ar_contracts.definitions.RoutineTrigger
  event_filter          text,                        -- JMESPath on the event envelope; truthy = run
  delivery              jsonb NOT NULL DEFAULT '[]', -- schema: ar_contracts.definitions.DeliveryTarget[]
  budget                jsonb NOT NULL,              -- schema: ar_contracts.runs.RunBudget
  max_runs_per_day      int NOT NULL DEFAULT 48 CHECK (max_runs_per_day BETWEEN 1 AND 10000),
  concurrency_policy    text NOT NULL DEFAULT 'skip' CHECK (concurrency_policy IN ('skip','buffer_one','allow')),
  status                text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','needs_review','disabled')),
  paused_reason         text,
  temporal_schedule_id  text,
  webhook_path_token    text UNIQUE,                 -- random token in /api/v1/hooks/routines/{token}
  webhook_secret_ref_id uuid REFERENCES secret_refs(id) ON DELETE SET NULL,
  consecutive_failures  int NOT NULL DEFAULT 0,
  last_run_at           timestamptz,
  next_run_at           timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  CHECK (run_as = 'owner' OR service_account_id IS NOT NULL)
);
CREATE INDEX ix_routines_tenant ON routines(tenant_id, status);
CREATE INDEX ix_routines_owner ON routines(tenant_id, owner_user_id);
ALTER TABLE runs ADD CONSTRAINT fk_runs_routine FOREIGN KEY (routine_id) REFERENCES routines(id) ON DELETE SET NULL;
ALTER TABLE standing_approvals ADD CONSTRAINT fk_sa_routine FOREIGN KEY (routine_id) REFERENCES routines(id) ON DELETE CASCADE;

CREATE TABLE routine_events (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  routine_id      uuid NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
  idempotency_key text NOT NULL,
  source          text NOT NULL CHECK (source IN ('schedule','webhook','slack','teams','email','s3','db','manual')),
  envelope        jsonb NOT NULL,                    -- schema: ar_contracts.events.EventEnvelope (payload truncated to 64 KiB)
  payload_file_id uuid REFERENCES files(id) ON DELETE SET NULL,
  status          text NOT NULL CHECK (status IN ('accepted','duplicate','filtered','rate_limited','skipped_concurrency','started','failed')),
  run_id          uuid REFERENCES runs(id) ON DELETE SET NULL,
  received_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (routine_id, idempotency_key)
);
CREATE INDEX ix_routine_events_routine ON routine_events(tenant_id, routine_id, received_at DESC);
```

## 14. Channels (`ar_domain.channels`)

```sql
CREATE TABLE channel_integrations (
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  kind             text NOT NULL CHECK (kind IN ('slack','teams','email','widget')),
  name             text NOT NULL,
  config           jsonb NOT NULL DEFAULT '{}',      -- schema: ar_contracts.definitions.ChannelConfig
  secret_ref_id    uuid REFERENCES secret_refs(id) ON DELETE RESTRICT,
  default_agent_id uuid REFERENCES agents(id) ON DELETE SET NULL,
  agent_routing    jsonb NOT NULL DEFAULT '[]',      -- [{match: {channel_id|keyword}, agent_id}]
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','error')),
  status_detail    text,
  created_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, kind, name)
);

CREATE TABLE channel_identities (
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  integration_id   uuid NOT NULL REFERENCES channel_integrations(id) ON DELETE CASCADE,
  external_user_id text NOT NULL,
  user_id          uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  match_method     text NOT NULL CHECK (match_method IN ('email','scim','manual_link')),
  verified_at      timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (integration_id, external_user_id)
);

CREATE TABLE channel_threads (
  id                  uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  integration_id      uuid NOT NULL REFERENCES channel_integrations(id) ON DELETE CASCADE,
  external_channel_id text NOT NULL,
  external_thread_id  text NOT NULL,
  conversation_id     uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (integration_id, external_channel_id, external_thread_id)
);

CREATE TABLE channel_posts (
  id                  uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  integration_id      uuid REFERENCES channel_integrations(id) ON DELETE CASCADE,
  thread_id           uuid REFERENCES channel_threads(id) ON DELETE SET NULL,
  direction           text NOT NULL CHECK (direction IN ('inbound','outbound')),
  kind                text NOT NULL CHECK (kind IN ('slack','teams','email','widget','webhook')),
  external_message_id text,
  body                text NOT NULL,
  status              text NOT NULL DEFAULT 'posted' CHECK (status IN ('posted','failed','pending')),
  detail              jsonb NOT NULL DEFAULT '{}',
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_channel_posts_tenant ON channel_posts(tenant_id, created_at);
```

`channel_posts` is the durable record of a channel message (OQ-41). Credential bytes stay in the secret store; this table stores the post.

## 15. Audit and usage (`ar_domain.audit`, `ar_domain.usage`)

```sql
CREATE TABLE audit_events (
  id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id            uuid REFERENCES tenants(id) ON DELETE RESTRICT,  -- NULL = platform-level event
  tenant_seq           bigint NOT NULL,              -- gapless per tenant (assigned under advisory lock)
  occurred_at          timestamptz NOT NULL DEFAULT now(),
  actor_type           text NOT NULL CHECK (actor_type IN ('user','service_account','agent','system','platform_admin')),
  actor_id             text NOT NULL,
  on_behalf_of_user_id uuid,
  action               text NOT NULL,               -- catalogue: docs/06-security/audit.md
  target_type          text NOT NULL,
  target_id            text,
  agent_id             uuid,
  run_id               uuid,
  tool_call_id         uuid,
  decision             text,                        -- allow|deny|require_approval|approve|reject
  outcome              text NOT NULL DEFAULT 'success' CHECK (outcome IN ('success','failure')),
  data_classification  text,
  ip                   inet,
  user_agent           text,
  trace_id             text,
  detail               jsonb NOT NULL DEFAULT '{}', -- redacted
  prev_hash            text NOT NULL,               -- previous event hash in this tenant chain (64 zeros for the first)
  hash                 text NOT NULL,               -- sha256(prev_hash || JCS(event fields except id, hash))
  UNIQUE NULLS NOT DISTINCT (tenant_id, tenant_seq)
);
CREATE INDEX ix_audit_tenant_time ON audit_events(tenant_id, occurred_at DESC);
CREATE INDEX ix_audit_action ON audit_events(tenant_id, action, occurred_at DESC);
CREATE INDEX ix_audit_actor ON audit_events(tenant_id, actor_id, occurred_at DESC);

CREATE TABLE usage_events (
  id           uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  occurred_at  timestamptz NOT NULL DEFAULT now(),
  metric       text NOT NULL CHECK (metric IN ('model_input_tokens','model_output_tokens','model_cached_tokens','embedding_tokens','rerank_requests','tool_calls','sandbox_cpu_seconds','sandbox_sessions','storage_bytes','runs')),
  quantity     bigint NOT NULL,
  cost_micros  bigint NOT NULL DEFAULT 0,
  user_id      uuid,
  team_id      uuid,
  agent_id     uuid,
  routine_id   uuid,
  run_id       uuid,
  model_id     uuid,
  model_alias  text,
  tool_id      uuid,
  source       text NOT NULL,                       -- emitting deployable
  dedupe_key   text NOT NULL,                       -- e.g. 'mg:{request_id}:in'
  UNIQUE (tenant_id, dedupe_key)
);
CREATE INDEX ix_usage_events_time ON usage_events(tenant_id, occurred_at);

CREATE TABLE usage_daily (
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  day         date NOT NULL,                         -- tenant timezone
  metric      text NOT NULL,
  user_id     uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
  team_id     uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
  agent_id    uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
  model_alias text NOT NULL DEFAULT '',
  quantity    bigint NOT NULL,
  cost_micros bigint NOT NULL,
  PRIMARY KEY (tenant_id, day, metric, user_id, team_id, agent_id, model_alias)
);

CREATE TABLE quotas (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  scope_type  text NOT NULL CHECK (scope_type IN ('tenant','team','user','agent')),
  scope_id    uuid,                                  -- NULL for 'tenant'; for 'user' NULL means "each user"
  metric      text NOT NULL CHECK (metric IN ('cost_micros','model_tokens','runs','sandbox_cpu_seconds','tool_calls')),
  period      text NOT NULL CHECK (period IN ('day','month')),
  limit_value bigint NOT NULL CHECK (limit_value >= 0),
  action      text NOT NULL DEFAULT 'block' CHECK (action IN ('block','warn')),
  warn_at_pct int NOT NULL DEFAULT 80 CHECK (warn_at_pct BETWEEN 1 AND 100),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (tenant_id, scope_type, scope_id, metric, period)
);
```

Plan-level limits (`plans.limits`) are enforced as implicit tenant quotas in SaaS mode ([spec 17](../03-specs/17-audit-usage-metering.md)).

## 16. Evaluation (`ar_domain.evals`)

```sql
CREATE TABLE eval_suites (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  agent_id    uuid REFERENCES agents(id) ON DELETE CASCADE,   -- NULL = reusable suite (e.g. red-team)
  name        text NOT NULL,
  description text NOT NULL DEFAULT '',
  kind        text NOT NULL DEFAULT 'functional' CHECK (kind IN ('functional','retrieval','safety','red_team')),
  gate        jsonb NOT NULL DEFAULT '{}',          -- schema: ar_contracts.evals.GateConfig
  created_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE eval_cases (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  suite_id    uuid NOT NULL REFERENCES eval_suites(id) ON DELETE CASCADE,
  name        text NOT NULL,
  input       jsonb NOT NULL,                       -- schema: ar_contracts.evals.EvalInput
  assertions  jsonb NOT NULL,                       -- schema: ar_contracts.evals.Assertion[]
  tool_mocks  jsonb NOT NULL DEFAULT '[]',          -- schema: ar_contracts.evals.ToolMock[]
  tags        text[] NOT NULL DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_eval_cases_suite ON eval_cases(tenant_id, suite_id);

CREATE TABLE eval_runs (
  id                   uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  suite_id             uuid NOT NULL REFERENCES eval_suites(id) ON DELETE CASCADE,
  agent_version_id     uuid REFERENCES agent_versions(id) ON DELETE SET NULL,
  model_alias_override text,
  status               text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','failed','cancelled')),
  summary              jsonb NOT NULL DEFAULT '{}', -- {cases, passed, pass_rate, mean_scores, cost_micros, p95_latency_ms, gate_passed}
  baseline_eval_run_id uuid REFERENCES eval_runs(id) ON DELETE SET NULL,
  temporal_workflow_id text NOT NULL,
  triggered_by         uuid REFERENCES users(id) ON DELETE SET NULL,
  trigger              text NOT NULL DEFAULT 'manual' CHECK (trigger IN ('manual','publish_gate','schedule','ci')),
  started_at           timestamptz,
  finished_at          timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_eval_runs_suite ON eval_runs(tenant_id, suite_id, created_at DESC);

CREATE TABLE eval_results (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  eval_run_id uuid NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  case_id     uuid NOT NULL REFERENCES eval_cases(id) ON DELETE CASCADE,
  run_id      uuid REFERENCES runs(id) ON DELETE SET NULL,
  passed      boolean NOT NULL,
  scores      jsonb NOT NULL DEFAULT '{}',           -- {assertion_name: {passed, score, reason}}
  output_text text NOT NULL DEFAULT '',
  latency_ms  int,
  cost_micros bigint NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (eval_run_id, case_id)
);
```

## 17. Events, webhooks, notifications, idempotency (`ar_domain.events`)

```sql
CREATE TABLE outbox_events (
  id           uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id    uuid REFERENCES tenants(id) ON DELETE CASCADE,
  topic        text NOT NULL,                        -- docs/05-contracts/domain-events.md
  payload      jsonb NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz,
  attempts     int NOT NULL DEFAULT 0
);
CREATE INDEX ix_outbox_unpublished ON outbox_events(created_at) WHERE published_at IS NULL;
CREATE INDEX ix_outbox_tenant ON outbox_events(tenant_id, created_at);

CREATE TABLE outbound_webhooks (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name          text NOT NULL,
  url           text NOT NULL CHECK (url ~ '^https://'),
  secret_ref_id uuid NOT NULL REFERENCES secret_refs(id) ON DELETE RESTRICT,
  topics        text[] NOT NULL,
  status        text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','failing')),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE webhook_deliveries (
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  webhook_id       uuid REFERENCES outbound_webhooks(id) ON DELETE CASCADE,   -- NULL for run callbacks
  target_url       text,                              -- run callback URL when webhook_id IS NULL
  outbox_event_id  uuid NOT NULL REFERENCES outbox_events(id) ON DELETE CASCADE,
  status           text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','succeeded','failed','dead')),
  attempts         int NOT NULL DEFAULT 0,
  last_status_code int,
  last_error       text,
  next_attempt_at  timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (webhook_id, outbox_event_id),
  UNIQUE (outbox_event_id, target_url),
  CHECK ((webhook_id IS NOT NULL) <> (target_url IS NOT NULL))
);
CREATE INDEX ix_webhook_deliveries_tenant ON webhook_deliveries(tenant_id, webhook_id, created_at DESC);

CREATE TABLE notifications (
  id         uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind       text NOT NULL CHECK (kind IN ('approval_requested','approval_decided','routine_failed','routine_paused','run_completed','tool_review_requested','tool_review_decided','quota_warning','ingestion_failed','credential_required','conversation_shared','routine_completed','export_ready','file_quarantined','memory_review_requested','eval_completed','system')),
  title      text NOT NULL,
  body       text NOT NULL DEFAULT '',
  link       text NOT NULL DEFAULT '',               -- relative web path, e.g. /approvals/{id}
  data       jsonb NOT NULL DEFAULT '{}',
  read_at    timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_notifications_user ON notifications(tenant_id, user_id, created_at DESC);
CREATE INDEX ix_notifications_unread ON notifications(tenant_id, user_id) WHERE read_at IS NULL;

CREATE TABLE idempotency_keys (
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  principal_id  text NOT NULL,
  key           text NOT NULL,
  request_hash  text NOT NULL,
  status_code   int,
  response_body jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, principal_id, key)
);
CREATE INDEX ix_idempotency_created ON idempotency_keys(created_at);   -- swept after 24 h
```

## 18. Triggers

- `set_updated_at` BEFORE UPDATE on every table with an `updated_at` column.
- `forbid_published_agent_version_update` BEFORE UPDATE on `agent_versions`: raises if `OLD.state = 'published'` and anything other than `state` (to `'superseded'`) and `updated_at` changes.
- `append_only` BEFORE UPDATE OR DELETE on `audit_events` and `policy_versions`: raises `'<table> is append-only'`. (Deleting a tenant: `audit_events` rows are exported then removed by the platform-owner role `ar_owner` during `TenantDeletionWorkflow` steps, which disables the trigger inside that transaction only.)
- `skill_versions_immutable` BEFORE UPDATE OR DELETE on `skill_versions`: raises when `OLD.version >= 1` (version `0` is the mutable draft working copy, [spec 14](../03-specs/14-skills.md)).
- `tool_versions_immutable` BEFORE UPDATE OR DELETE on `tool_versions`: raises when the parent `tool_server_versions.review_status = 'approved'`, except updates that change only `embedding` (computed after approval).
- Audit retention: `RetentionSweepWorkflow` never deletes `audit_events` directly. After `AuditExportWorkflow` has written the archive object for the range, it calls `SELECT purge_audit_events(:tenant_id, :before)` as `ar_platform`. The function is `SECURITY DEFINER` (owner `ar_owner`), refuses `before > now() - interval '1 year'`, sets `SET LOCAL session_replication_role = replica` inside the function, deletes rows with `occurred_at < before` for that tenant, and returns the count. `EXECUTE` is granted only to `ar_platform`. Created in revision 0003.
- Tenant deletion: all immutability triggers above (and `append_only`) are bypassed only inside `TenantDeletionWorkflow` delete transactions, executed as `ar_owner` with `SET LOCAL session_replication_role = replica` after the audit export has completed.

## 19. Table index (74 tables)

| Tables | Module | Section |
|---|---|---|
| plans, tenants, tenant_domains, identity_providers, users, groups, group_members, teams, team_members, roles, service_accounts, role_assignments, api_keys, scim_tokens, invitations, support_access_grants | identity | 1 |
| secret_refs, encrypted_secrets, credential_providers, credential_grants | secrets | 2 |
| model_providers, models, model_aliases | models | 3 |
| agents, agent_versions, agent_version_bindings | agents | 4 |
| conversations, conversation_shares, runs, messages, message_feedback, run_steps, run_events | conversations / runs | 5 |
| data_connections, tool_servers, tool_server_versions, tools, tool_versions, tool_calls | tools | 6 |
| policies, policy_versions, approvals, approval_decisions, standing_approvals | policy / approvals | 7 |
| knowledge_collections, knowledge_sources, documents, document_chunks, chunk_embeddings, ingestion_jobs | knowledge | 8 |
| memory_facts | memory | 9 |
| sandbox_templates, sandboxes | sandboxes | 10 |
| files | files | 11 |
| skills, skill_versions | skills | 12 |
| routines, routine_events | routines | 13 |
| channel_integrations, channel_identities, channel_threads, channel_posts | channels | 14 |
| audit_events, usage_events, usage_daily, quotas | audit / usage | 15 |
| eval_suites, eval_cases, eval_runs, eval_results | evals | 16 |
| outbox_events, outbound_webhooks, webhook_deliveries, notifications, idempotency_keys | events | 17 |

Sections 20–28 are additive. They do not change sections 0–19. Revision numbers are in [migrations §3](migrations.md#3-initial-revision-plan). The M1 seed and M1 tasks do not create these tables.

## 20. Content packs (`ar_domain.agents`)

```sql
CREATE TABLE installed_packs (
  id                uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  pack_id           text NOT NULL CHECK (pack_id ~ '^[a-z][a-z0-9_]{1,40}$'),
  version           text NOT NULL,                         -- semver
  status            text NOT NULL DEFAULT 'installed' CHECK (status IN ('installed','uninstalled')),
  manifest          jsonb NOT NULL,                        -- schema: ar_contracts.definitions.ContentPack
  manifest_hash     text NOT NULL,
  signature         text,
  signature_key_id  text,
  installed_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  installed_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, pack_id, version)
);
CREATE INDEX ix_installed_packs_tenant ON installed_packs(tenant_id, pack_id);

CREATE TABLE installed_pack_resources (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  pack_row_id   uuid NOT NULL REFERENCES installed_packs(id) ON DELETE CASCADE,
  kind          text NOT NULL,
  slug          text NOT NULL,
  resource_id   uuid NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (pack_row_id, kind, slug)
);
CREATE INDEX ix_installed_pack_resources_tenant ON installed_pack_resources(tenant_id);
```

## 21. Reviews and segregation of duties (`ar_domain.approvals`)

```sql
CREATE TABLE review_queues (
  id                   uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  slug                 citext NOT NULL,
  name                 text NOT NULL,
  subject_type         text NOT NULL CHECK (subject_type IN ('artifact','file','message','evidence_item','run_record','agent_card','binder','pack_record')),
  levels               jsonb NOT NULL,                     -- schema: ar_contracts.reviews.ReviewLevel[]
  statement_template   text NOT NULL,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);
CREATE INDEX ix_review_queues_tenant ON review_queues(tenant_id);

CREATE TABLE review_items (
  id                      uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id               uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  queue_id                uuid NOT NULL REFERENCES review_queues(id) ON DELETE RESTRICT,
  subject_type            text NOT NULL,
  subject_id              uuid NOT NULL,
  subject_ref             jsonb NOT NULL DEFAULT '{}',     -- pack_record: {pack_id, record_class, record_id}
  content_hash            text NOT NULL,
  statement_text          text NOT NULL,
  statement_hash          text NOT NULL,
  status                  text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_review','signed','rejected','expired','superseded')),
  current_level           int NOT NULL DEFAULT 1,
  preparer_principal_type text NOT NULL CHECK (preparer_principal_type IN ('user','service_account','guest')),
  preparer_principal_id   uuid NOT NULL,
  expires_at              timestamptz,
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_review_items_queue ON review_items(tenant_id, queue_id, status);
CREATE INDEX ix_review_items_subject ON review_items(tenant_id, subject_type, subject_id);

CREATE TABLE signoffs (                                   -- append-only
  id                      uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id               uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  review_item_id          uuid NOT NULL REFERENCES review_items(id) ON DELETE RESTRICT,
  level                   int NOT NULL,
  decision                text NOT NULL CHECK (decision IN ('approve','reject','delegate')),
  signer_principal_type   text NOT NULL CHECK (signer_principal_type IN ('user','guest')),
  signer_principal_id     uuid NOT NULL,
  signer_role_key         text,
  content_hash            text NOT NULL,
  statement_hash          text NOT NULL,
  comment                 text NOT NULL DEFAULT '',
  step_up_at              timestamptz,
  delegated_to_user_id    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_signoffs_item ON signoffs(tenant_id, review_item_id, level);

CREATE TABLE sod_constraints (
  id           uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  kind         text NOT NULL DEFAULT 'conflicting_roles' CHECK (kind IN ('conflicting_roles')),
  role_a       text NOT NULL,
  role_b       text NOT NULL,
  applies_to   text NOT NULL CHECK (applies_to IN ('approval','signoff','both')),
  enabled      boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (role_a <> role_b),
  UNIQUE (tenant_id, role_a, role_b, applies_to)
);
CREATE INDEX ix_sod_constraints_tenant ON sod_constraints(tenant_id);
```

Trigger `append_only` on `signoffs`.

## 22. Run records (`ar_domain.runs`)

```sql
CREATE TABLE run_records (                                -- append-only
  id                       uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id                uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  run_id                   uuid NOT NULL UNIQUE REFERENCES runs(id) ON DELETE RESTRICT,
  agent_id                 uuid NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
  agent_version_id         uuid NOT NULL REFERENCES agent_versions(id) ON DELETE RESTRICT,
  definition_hash          text NOT NULL,
  prompt_template_hashes   jsonb NOT NULL,
  model_id                 text NOT NULL,
  model_revision           text,
  weights_digest           text,
  sampling_params          jsonb NOT NULL,
  retrieved                jsonb NOT NULL DEFAULT '[]',
  output_sha256            text NOT NULL,
  manifest_sha256          text NOT NULL,
  signature                text NOT NULL,
  signature_key_id         text NOT NULL,
  tool_io_evidence_id      uuid,                          -- FK added in section 23
  retention_class          text NOT NULL DEFAULT 'run_record',
  sealed_at                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_run_records_tenant ON run_records(tenant_id, sealed_at DESC);
CREATE INDEX ix_run_records_agent ON run_records(tenant_id, agent_id);

CREATE TABLE run_record_replays (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  run_record_id   uuid NOT NULL REFERENCES run_records(id) ON DELETE RESTRICT,
  status          text NOT NULL CHECK (status IN ('running','matched','diverged','failed')),
  divergence      jsonb,
  started_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  started_at      timestamptz NOT NULL DEFAULT now(),
  completed_at    timestamptz
);
CREATE INDEX ix_run_record_replays_record ON run_record_replays(tenant_id, run_record_id);
```

Trigger `append_only` on `run_records`.

## 23. Evidence vault (`ar_domain.records`)

```sql
CREATE TABLE evidence_items (
  id                        uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id                 uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  status                    text NOT NULL DEFAULT 'sealed' CHECK (status IN ('sealed','disposed')),
  content_sha256            text NOT NULL,
  size_bytes                bigint NOT NULL CHECK (size_bytes >= 0),
  media_type                text NOT NULL,
  storage_key               text NOT NULL,
  worm_locked_until         timestamptz NOT NULL,
  rfc3161_token             bytea,
  signature                 text NOT NULL,
  signature_key_id          text NOT NULL,
  source_system             text NOT NULL,
  collection_method         text NOT NULL CHECK (collection_method IN ('api','tool_call','upload','browser_screenshot','sandbox','run_record')),
  collected_at              timestamptz NOT NULL,
  collector_run_id          uuid,
  collector_tool_call_id    uuid,
  collector_principal_type  text NOT NULL CHECK (collector_principal_type IN ('user','service_account','system')),
  collector_principal_id    uuid,
  provenance                jsonb NOT NULL,               -- schema: ar_contracts.records.EvidenceProvenance
  classification            text NOT NULL DEFAULT 'internal' CHECK (classification IN ('public','internal','confidential','restricted')),
  legal_hold                boolean NOT NULL DEFAULT false,
  retention_class           text NOT NULL DEFAULT 'evidence_item',
  created_at                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_evidence_items_tenant ON evidence_items(tenant_id, collected_at DESC);
CREATE UNIQUE INDEX ux_evidence_storage_key ON evidence_items(tenant_id, storage_key);

CREATE TABLE evidence_custody_events (                    -- append-only
  id                    uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id             uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  evidence_item_id      uuid NOT NULL REFERENCES evidence_items(id) ON DELETE RESTRICT,
  action                text NOT NULL CHECK (action IN ('captured','accessed','exported','verified','hold_applied','hold_released','disposed')),
  actor_principal_type  text NOT NULL,
  actor_principal_id    uuid,
  detail                jsonb NOT NULL DEFAULT '{}',
  audit_event_id        bigint,
  created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_evidence_custody_item ON evidence_custody_events(tenant_id, evidence_item_id, created_at);

ALTER TABLE run_records
  ADD CONSTRAINT fk_run_records_evidence
  FOREIGN KEY (tool_io_evidence_id) REFERENCES evidence_items(id) ON DELETE RESTRICT;
```

Trigger `evidence_items_immutable`: UPDATE may change only `status`, `legal_hold` and `worm_locked_until`. DELETE is rejected. Trigger `append_only` on `evidence_custody_events`.

## 24. Legal hold and retention (`ar_domain.records`)

```sql
CREATE TABLE legal_holds (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  matter             text NOT NULL,
  custodians         jsonb NOT NULL DEFAULT '[]',      -- user ids
  scope_query        jsonb NOT NULL,                   -- schema: ar_contracts.records.HoldScope
  status             text NOT NULL DEFAULT 'active' CHECK (status IN ('active','released')),
  approver_user_id   uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_by         uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  started_at         timestamptz NOT NULL DEFAULT now(),
  released_at        timestamptz,
  release_reason     text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_legal_holds_tenant ON legal_holds(tenant_id, status);

CREATE TABLE legal_hold_members (
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  hold_id       uuid NOT NULL REFERENCES legal_holds(id) ON DELETE CASCADE,
  record_class  text NOT NULL CHECK (record_class IN (
                  'conversation','run','run_record','evidence_item','document','file',
                  'memory_fact','signoff','agent_card','audit_archive')),
  record_id     uuid NOT NULL,
  detail        jsonb NOT NULL DEFAULT '{}',           -- previous_retention_class
  applied_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (hold_id, record_class, record_id)
);
CREATE INDEX ix_legal_hold_members_record ON legal_hold_members(tenant_id, record_class, record_id);

CREATE TABLE retention_schedules (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  record_class    text NOT NULL,
  retention_days  int NOT NULL CHECK (retention_days >= 1),
  disposition     text NOT NULL CHECK (disposition IN ('delete','archive_then_delete','keep')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, record_class)
);
CREATE INDEX ix_retention_schedules_tenant ON retention_schedules(tenant_id);

CREATE TABLE disposition_certificates (                  -- append-only
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  record_class       text NOT NULL,
  record_id          uuid NOT NULL,
  content_sha256     text NOT NULL,
  method             text NOT NULL,
  disposed_at        timestamptz NOT NULL DEFAULT now(),
  certificate_hash   text NOT NULL,
  actor_user_id      uuid REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX ix_disposition_certificates_tenant ON disposition_certificates(tenant_id, disposed_at DESC);
```

Trigger `append_only` on `disposition_certificates`.

## 25. AI governance register (`ar_domain.agents`)

```sql
CREATE TABLE agent_cards (
  id                  uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  agent_id            uuid NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
  agent_version_id    uuid NOT NULL UNIQUE REFERENCES agent_versions(id) ON DELETE RESTRICT,
  purpose             text NOT NULL,
  risk_tier           text NOT NULL,
  data_categories     text[] NOT NULL DEFAULT '{}',
  oversight_mode      text NOT NULL CHECK (oversight_mode IN ('autonomous_r0','approval','human_in_loop')),
  eval_summary        jsonb,
  known_limitations   text NOT NULL DEFAULT '',
  owner_user_id       uuid REFERENCES users(id) ON DELETE SET NULL,
  review_due_at       date,
  card_hash           text NOT NULL,
  published_at        timestamptz NOT NULL DEFAULT now(),
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_agent_cards_agent ON agent_cards(tenant_id, agent_id);

CREATE TABLE ai_incidents (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id          uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  agent_id           uuid REFERENCES agents(id) ON DELETE SET NULL,
  agent_version_id   uuid REFERENCES agent_versions(id) ON DELETE SET NULL,
  run_id             uuid REFERENCES runs(id) ON DELETE SET NULL,
  severity           text NOT NULL CHECK (severity IN ('low','medium','high')),
  summary            text NOT NULL,
  status             text NOT NULL DEFAULT 'open' CHECK (status IN ('open','mitigated','closed')),
  detected_at        timestamptz NOT NULL DEFAULT now(),
  closed_at          timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_incidents_tenant ON ai_incidents(tenant_id, status);

CREATE TABLE ai_oversight_daily (
  tenant_id              uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  agent_id               uuid NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  day                    date NOT NULL,
  approvals_requested    int NOT NULL DEFAULT 0,
  approvals_approved     int NOT NULL DEFAULT 0,
  approvals_rejected     int NOT NULL DEFAULT 0,
  signoffs_approved      int NOT NULL DEFAULT 0,
  signoffs_rejected      int NOT NULL DEFAULT 0,
  overrides              int NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant_id, agent_id, day)
);
```

`agent_cards` trigger `agent_cards_limited_update` allows UPDATE only of `known_limitations`, `review_due_at`, `data_categories` and `card_hash`.

## 26. Guest principals (`ar_domain.identity`)

Created by M14-T11. M1 does not read or write these tables.

```sql
CREATE TABLE guest_principals (
  id                   uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email                citext NOT NULL,
  display_name         text NOT NULL,
  kind                 text NOT NULL CHECK (kind IN ('external','partner','other')),
  status               text NOT NULL DEFAULT 'invited' CHECK (status IN ('invited','active','expired','revoked')),
  auth_method          text NOT NULL CHECK (auth_method IN ('magic_link_totp','federated')),
  totp_secret_ref_id   uuid,                              -- FK to secret_refs, added in the same revision
  federated_subject    text,
  invited_by_user_id   uuid REFERENCES users(id) ON DELETE SET NULL,
  expires_at           timestamptz NOT NULL,
  last_login_at        timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, email)
);
CREATE INDEX ix_guest_principals_tenant ON guest_principals(tenant_id, status);

ALTER TABLE guest_principals
  ADD CONSTRAINT fk_guest_totp_secret FOREIGN KEY (totp_secret_ref_id) REFERENCES secret_refs(id) ON DELETE SET NULL;

CREATE TABLE guest_grants (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  guest_id      uuid NOT NULL REFERENCES guest_principals(id) ON DELETE CASCADE,
  portal        text NOT NULL CHECK (portal ~ '^[a-z][a-z0-9_]{0,40}$'),
  scope         jsonb NOT NULL,                           -- {evidence_ids, binder_ids, pack_record_ids}
  expires_at    timestamptz NOT NULL,
  watermark     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_guest_grants_guest ON guest_grants(tenant_id, guest_id);

CREATE TABLE guest_login_challenges (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  guest_id      uuid NOT NULL REFERENCES guest_principals(id) ON DELETE CASCADE,
  token_hash    text NOT NULL UNIQUE,
  expires_at    timestamptz NOT NULL,
  consumed_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_guest_login_challenges_guest ON guest_login_challenges(tenant_id, guest_id);
```

## 27. Binder exports (`ar_domain.records`)

```sql
CREATE TABLE binder_exports (
  id                uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  title             text NOT NULL,
  status            text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_review','building','ready','failed')),
  selection         jsonb NOT NULL,
  require_review    boolean NOT NULL DEFAULT false,
  review_item_id    uuid REFERENCES review_items(id) ON DELETE SET NULL,
  manifest_sha256   text,
  file_id           uuid REFERENCES files(id) ON DELETE SET NULL,
  created_by        uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  completed_at      timestamptz
);
CREATE INDEX ix_binder_exports_tenant ON binder_exports(tenant_id, created_at DESC);
```

`files.kind` for the ZIP is the existing value `export`.

## 28. Pack enablement (`ar_domain.packs`)

```sql
CREATE TABLE pack_registrations (                         -- platform-or-own; tenant_id NULL = built-in registration
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id     uuid REFERENCES tenants(id) ON DELETE CASCADE,
  pack_id       text NOT NULL,
  version       text NOT NULL,
  manifest      jsonb NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (pack_id, version)
);

CREATE TABLE tenant_pack_flags (
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  pack_id     text NOT NULL,
  enabled     boolean NOT NULL DEFAULT false,
  settings    jsonb NOT NULL DEFAULT '{}',
  updated_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, pack_id)
);
```

`pack_registrations` uses the platform-or-own RLS policy ([rls §3.2](rls.md#32-platform-or-own-tables-tenant_id-nullable)). `tenant_pack_flags` is tenant-owned.

## 29. Triggers added with sections 20–28

- `append_only` on `signoffs`, `run_records`, `evidence_custody_events`, `disposition_certificates`.
- `evidence_items_immutable` on `evidence_items` (see §23).
- `agent_cards_limited_update` on `agent_cards` (see §25).
- Tenant deletion bypasses these triggers only inside `TenantDeletionWorkflow`, with the same `session_replication_role` rule as §18, and only after a binder of the tenant's evidence manifests has been written to the audit archive.

## 30. Table index (additions, 23 tables)

| Tables | Module | Section |
|---|---|---|
| installed_packs, installed_pack_resources | agents | 20 |
| review_queues, review_items, signoffs, sod_constraints | approvals | 21 |
| run_records, run_record_replays | runs | 22 |
| evidence_items, evidence_custody_events | records | 23 |
| legal_holds, legal_hold_members, retention_schedules, disposition_certificates | records | 24 |
| agent_cards, ai_incidents, ai_oversight_daily | agents | 25 |
| guest_principals, guest_grants, guest_login_challenges | identity | 26 |
| binder_exports | records | 27 |
| pack_registrations, tenant_pack_flags | packs | 28 |

Core total is 97 tables: 74 in §19 plus these 23. The GRC pack schema is not in this list ([10-grc-pack/domain-model.md](../10-grc-pack/domain-model.md)).
