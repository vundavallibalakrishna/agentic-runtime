-- Reversible schema for the GRC pack. Core does not own these tables.
-- The process store is what the API reads today, matching the records pack.
-- Apply this file when a deployment wants the rows in Postgres.

CREATE SCHEMA IF NOT EXISTS grc_pack;

CREATE TABLE IF NOT EXISTS grc_pack.catalogues (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    name text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS grc_pack.catalogue_items (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    catalogue_id uuid NOT NULL REFERENCES grc_pack.catalogues (id),
    item_key text NOT NULL,
    title text NOT NULL,
    statement text NOT NULL
);

CREATE TABLE IF NOT EXISTS grc_pack.evidence_links (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    item_id uuid NOT NULL,
    evidence_id uuid NOT NULL,
    note text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS grc_pack.risks (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    title text NOT NULL,
    score integer NOT NULL,
    status text NOT NULL
);

CREATE TABLE IF NOT EXISTS grc_pack.findings (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    title text NOT NULL,
    item_key text NOT NULL DEFAULT '',
    status text NOT NULL
);

ALTER TABLE grc_pack.catalogues ENABLE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.catalogue_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.evidence_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.risks ENABLE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.findings ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON grc_pack.catalogues
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY tenant_isolation ON grc_pack.catalogue_items
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY tenant_isolation ON grc_pack.evidence_links
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY tenant_isolation ON grc_pack.risks
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY tenant_isolation ON grc_pack.findings
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
