-- Reversible schema for the GRC pack. Core does not own these tables.
-- The API persists rows in public.extension_rows. Apply this file when a
-- deployment also wants the relational shape. It follows the core RLS helper:
-- FORCE, WITH CHECK, app_tenant_id(), and the service grants.

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
    statement text NOT NULL,
    UNIQUE (catalogue_id, item_key)
);

CREATE TABLE IF NOT EXISTS grc_pack.evidence_links (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    item_id uuid NOT NULL REFERENCES grc_pack.catalogue_items (id),
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
ALTER TABLE grc_pack.catalogues FORCE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.catalogue_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.catalogue_items FORCE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.evidence_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.evidence_links FORCE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.risks ENABLE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.risks FORCE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE grc_pack.findings FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON grc_pack.catalogues
    USING (tenant_id = app_tenant_id())
    WITH CHECK (tenant_id = app_tenant_id());
CREATE POLICY tenant_isolation ON grc_pack.catalogue_items
    USING (tenant_id = app_tenant_id())
    WITH CHECK (tenant_id = app_tenant_id());
CREATE POLICY tenant_isolation ON grc_pack.evidence_links
    USING (tenant_id = app_tenant_id())
    WITH CHECK (tenant_id = app_tenant_id());
CREATE POLICY tenant_isolation ON grc_pack.risks
    USING (tenant_id = app_tenant_id())
    WITH CHECK (tenant_id = app_tenant_id());
CREATE POLICY tenant_isolation ON grc_pack.findings
    USING (tenant_id = app_tenant_id())
    WITH CHECK (tenant_id = app_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON grc_pack.catalogues TO ar_app, ar_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON grc_pack.catalogue_items TO ar_app, ar_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON grc_pack.evidence_links TO ar_app, ar_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON grc_pack.risks TO ar_app, ar_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON grc_pack.findings TO ar_app, ar_platform;
GRANT SELECT ON grc_pack.catalogues TO ar_readonly;
GRANT SELECT ON grc_pack.catalogue_items TO ar_readonly;
GRANT SELECT ON grc_pack.evidence_links TO ar_readonly;
GRANT SELECT ON grc_pack.risks TO ar_readonly;
GRANT SELECT ON grc_pack.findings TO ar_readonly;
