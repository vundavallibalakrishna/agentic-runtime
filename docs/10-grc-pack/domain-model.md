# GRC pack domain model

Postgres schema `grc`. Alembic environment `packs/grc`, version table `grc_alembic_version` ([migrations §6](../04-data/migrations.md#6-pack-schemas), [OQ-28](../open-questions.md)). Every table has `tenant_id` and uses `enable_tenant_rls`. Column conventions match [schema §0](../04-data/schema.md#0-conventions). Evidence bytes stay in the core vault; this schema stores links only.

The pack must not add columns to core tables. `evidence_links.evidence_item_id` references `evidence_items(id)` as a cross-schema foreign key granted to `ar_app`.

## Tables

```sql
CREATE SCHEMA IF NOT EXISTS grc;

CREATE TABLE grc.frameworks (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key text NOT NULL,
  name text NOT NULL,
  version text NOT NULL,
  licence text NOT NULL CHECK (licence IN ('free','skeleton')),
  pack_owned boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, key, version)
);

CREATE TABLE grc.requirements (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  framework_id uuid NOT NULL REFERENCES grc.frameworks(id) ON DELETE CASCADE,
  key text NOT NULL,
  title text NOT NULL,
  statement text NOT NULL DEFAULT '',
  UNIQUE (framework_id, key)
);

CREATE TABLE grc.controls (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  framework_id uuid REFERENCES grc.frameworks(id) ON DELETE CASCADE,
  key text NOT NULL,
  title text NOT NULL,
  statement text NOT NULL DEFAULT '',
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, framework_id, key)
);

CREATE TABLE grc.control_mappings (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  from_control_id uuid NOT NULL REFERENCES grc.controls(id) ON DELETE CASCADE,
  to_control_id uuid NOT NULL REFERENCES grc.controls(id) ON DELETE CASCADE,
  confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  rationale text NOT NULL DEFAULT '',
  status text NOT NULL CHECK (status IN ('suggested','confirmed','rejected')),
  suggested_by uuid,
  confirmed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  confirmed_at timestamptz,
  CHECK (from_control_id <> to_control_id),
  UNIQUE (tenant_id, from_control_id, to_control_id)
);

CREATE TABLE grc.control_tests (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  control_id uuid NOT NULL REFERENCES grc.controls(id) ON DELETE CASCADE,
  key text NOT NULL,
  procedure text NOT NULL,
  schedule text NOT NULL,
  freshness_days int NOT NULL CHECK (freshness_days >= 1),
  UNIQUE (control_id, key)
);

CREATE TABLE grc.test_results (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  test_id uuid NOT NULL REFERENCES grc.control_tests(id) ON DELETE CASCADE,
  run_id uuid,
  run_record_id uuid,
  outcome text NOT NULL CHECK (outcome IN ('pass','fail','error')),
  evidence_item_id uuid,
  detail jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.evidence_links (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  control_id uuid NOT NULL REFERENCES grc.controls(id) ON DELETE CASCADE,
  evidence_item_id uuid NOT NULL REFERENCES evidence_items(id) ON DELETE RESTRICT,
  freshness_days int NOT NULL CHECK (freshness_days >= 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (control_id, evidence_item_id)
);

CREATE TABLE grc.assets (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name text NOT NULL,
  kind text NOT NULL,
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.risks (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  asset_id uuid REFERENCES grc.assets(id) ON DELETE SET NULL,
  title text NOT NULL,
  statement text NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','treating','accepted','closed')),
  source text NOT NULL DEFAULT 'human' CHECK (source IN ('human','agent')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.risk_assessments (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  risk_id uuid NOT NULL REFERENCES grc.risks(id) ON DELETE CASCADE,
  likelihood int NOT NULL CHECK (likelihood BETWEEN 1 AND 5),
  impact int NOT NULL CHECK (impact BETWEEN 1 AND 5),
  score int NOT NULL,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (score = likelihood * impact)
);

CREATE TABLE grc.treatments (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  risk_id uuid NOT NULL REFERENCES grc.risks(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('mitigate','transfer','avoid')),
  plan text NOT NULL,
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  due_at timestamptz,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','done'))
);

CREATE TABLE grc.vendors (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name text NOT NULL,
  tier text CHECK (tier IN ('critical','high','medium','low')),
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE grc.vendor_assessments (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  vendor_id uuid NOT NULL REFERENCES grc.vendors(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('intake','questionnaire','document_review')),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','scored')),
  tier text,
  rationale text NOT NULL DEFAULT '',
  due_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.findings (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  control_id uuid REFERENCES grc.controls(id) ON DELETE SET NULL,
  evidence_item_id uuid,
  title text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  due_at timestamptz,
  closure_evidence_item_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.issues (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  finding_id uuid REFERENCES grc.findings(id) ON DELETE SET NULL,
  title text NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','done')),
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  due_at timestamptz,
  external_ref text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.policies (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key text NOT NULL,
  title text NOT NULL,
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, key)
);

CREATE TABLE grc.policy_versions (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  policy_id uuid NOT NULL REFERENCES grc.policies(id) ON DELETE CASCADE,
  version int NOT NULL,
  body_md text NOT NULL,
  content_hash text NOT NULL,
  state text NOT NULL CHECK (state IN ('draft','published')),
  review_item_id uuid,
  UNIQUE (policy_id, version)
);

CREATE TABLE grc.obligations (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  regulator text NOT NULL,
  citation text NOT NULL,
  statement text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired')),
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  UNIQUE (tenant_id, regulator, citation)
);

CREATE TABLE grc.regulatory_changes (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  feed_id uuid,
  title text NOT NULL,
  url text NOT NULL,
  published_on date,
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new','triaged','dismissed')),
  note text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.incidents (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  title text NOT NULL,
  summary text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','notified','closed')),
  detected_at timestamptz NOT NULL,
  clocks jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.campaigns (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('questionnaire','vendor','acknowledgement','attestation','access_review')),
  title text NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','running','closed')),
  due_at timestamptz,
  audience jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.campaign_items (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  campaign_id uuid NOT NULL REFERENCES grc.campaigns(id) ON DELETE CASCADE,
  assignee_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  assignee_guest_id uuid,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','decided')),
  decision text,
  statement_text text NOT NULL DEFAULT '',
  statement_hash text,
  review_item_id uuid,
  UNIQUE (campaign_id, assignee_user_id, assignee_guest_id)
);

CREATE TABLE grc.answer_library (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  question text NOT NULL,
  answer_md text NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','expired')),
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  expires_at timestamptz,
  citations jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.pbc_requests (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  title text NOT NULL,
  control_id uuid REFERENCES grc.controls(id) ON DELETE SET NULL,
  owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','responded','accepted')),
  response_md text NOT NULL DEFAULT '',
  due_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.entitlements (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  source text NOT NULL CHECK (source IN ('okta','entra','google')),
  subject text NOT NULL,
  entitlement text NOT NULL,
  collected_at timestamptz NOT NULL,
  evidence_item_id uuid,
  UNIQUE (tenant_id, source, subject, entitlement)
);

CREATE TABLE grc.sod_rules (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name text NOT NULL,
  entitlement_a text NOT NULL,
  entitlement_b text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (entitlement_a <> entitlement_b),
  UNIQUE (tenant_id, entitlement_a, entitlement_b)
);
```

Indexes on `(tenant_id)` are created for every table, matching the core rule. `grc.sod_rules` is business segregation of duties for entitlements. Platform action segregation stays in core `sod_constraints`.

## Extended records

Same migration family, added by M16-T07, M18-T07, M18-T08, M19-T06, M19-T07 and M19-T08. They do not exist in core.

```sql
CREATE TABLE grc.entities (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  parent_id uuid REFERENCES grc.entities(id) ON DELETE RESTRICT,
  name text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('legal_entity','division','region')),
  UNIQUE (tenant_id, name)
);

CREATE TABLE grc.exceptions (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  control_id uuid NOT NULL REFERENCES grc.controls(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('exception','waiver')),
  rationale text NOT NULL,
  compensating_control_id uuid,
  expires_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status IN ('proposed','signed','expired','revoked')),
  review_item_id uuid
);

CREATE TABLE grc.ethics_cases (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  title text NOT NULL,
  status text NOT NULL CHECK (status IN ('open','investigating','closed')),
  restricted boolean NOT NULL DEFAULT true,
  opened_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.inspections (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  regulator text NOT NULL,
  started_on date NOT NULL,
  status text NOT NULL CHECK (status IN ('announced','in_progress','closed')),
  binder_id uuid
);

CREATE TABLE grc.dsar_requests (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  request_type text NOT NULL CHECK (request_type IN ('access','correction','erasure','portability')),
  due_at timestamptz NOT NULL,
  status text NOT NULL CHECK (status IN ('open','fulfilled','refused')),
  evidence_item_id uuid
);

CREATE TABLE grc.consent_records (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  subject_ref text NOT NULL,
  purpose text NOT NULL,
  state text NOT NULL CHECK (state IN ('granted','withdrawn')),
  evidence_item_id uuid,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE grc.resilience_tests (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('bcp','dr')),
  tested_on date NOT NULL,
  outcome text NOT NULL CHECK (outcome IN ('pass','fail','partial')),
  evidence_item_id uuid
);
```

`grc.exceptions.compensating_control_id` references `grc.controls`. A model-risk entry is a `grc.assets` row with `kind='model'`, linked to a core agent card only when the model is an agent on this platform. ESG metrics are `grc.obligations` plus evidence, not a separate taxonomy.

## Regulator feed catalogue

Created in the same migration as the tables above:

```sql
CREATE TABLE grc.regulator_feeds (
  id uuid PRIMARY KEY DEFAULT uuidv7(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  regulator text NOT NULL,
  url text NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  UNIQUE (tenant_id, regulator)
);
```

Seeded as pack data, not tenant rows, and copied into `grc.regulator_feeds` when a tenant enables the pack:

| Regulator | Starting URL |
|---|---|
| RBI | `https://www.rbi.org.in/Scripts/BS_ViewMasterCirculars.aspx` |
| SEBI | `https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=1&smid=0` |
| CERT-In | `https://www.cert-in.org.in/` |
| MeitY / DPB | `https://www.meity.gov.in/documents` |
| IRDAI | `https://irdai.gov.in/circulars` |
| EUR-Lex | `https://eur-lex.europa.eu/homepage.html` |

The watcher stores fetched pages as knowledge documents in a pack-owned collection and as `grc.regulatory_changes` rows. It does not scrape past `robots.txt`.
