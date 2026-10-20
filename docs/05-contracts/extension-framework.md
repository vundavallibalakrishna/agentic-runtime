# Extension framework

Core stays industry-agnostic. Anything a customer or a solution pack adds goes through one of the two extension paths below. Neither path edits `libs/` or `services/`.

## 1. Connector plugins

For a system the agent should call or ingest. Contract: [connector-sdk](connector-sdk.md). The server is an MCP process. The tenant registers it as a tool server ([spec 08](../03-specs/08-tool-registry-mcp.md)). No pack schema is required.

The testing kit is `ar_connector_sdk.testing`: `ToolServerHarness` and `conformance.run`.

## 2. Solution packs

For domain tables, HTTP routes, permissions, audit actions, agent templates, and UI. The first pack is [GRC](../10-grc-pack/README.md). Hooks are [spec 21 §6](../03-specs/21-records-governance.md#6-pack-extension-points) (M14-T13). Content-pack lifecycle is [spec 05 §10](../03-specs/05-agent-registry.md#10-content-packs).

| Concern | Rule |
|---|---|
| Packaging | Directory `packs/<pack_id>/`, Python package `ar_pack_<pack_id>`, optional uv workspace member. Import-linter contract `packs-not-in-core` forbids `ar_pack_*` from `libs/` and `services/`. |
| Manifest | `kind: ContentPack` ([definition-schema §11.2](definition-schema.md#112-content-pack-kind-contentpack)). `metadata.id`, `metadata.version` (semver), `metadata.minPlatform`. |
| Versioning | Upgrade requires a strictly greater semver. Pack Alembic is a separate history ([OQ-28](../open-questions.md)). |
| Install, upgrade, uninstall | `POST /api/v1/content-packs:install`, `:upgrade`, `:uninstall`. Signature over the JCS SHA-256 when `AR_PACK_SIGNATURE_REQUIRED` is true. Uninstall keeps data unless `dropSchema: true` with step-up. A legal hold that covers a pack row returns 409 `hold_active`. |
| Permissions | `register_pack_permissions`. Keys `{pack_id}.{resource}:{verb}`. Not in the M1 seed. |
| Audit | `register_pack_audit_actions`. Names `{pack_id}.{resource}.{verb}`. |
| Config schema | Manifest `spec.extension.configSchema` is a JSON Schema object. Values live in `tenant_pack_flags.settings`. Every property has a `default`. Missing settings mean the defaults. The pack settings screen is Simple (the properties with `x-ar-simple: true`) and Advanced (the rest, plus the raw JSON). |
| UI contribution points | Manifest `spec.extension.ui`: `nav` (href, label, permission), `settings` (href), `guestPortals` (portal name), `admin` (href). The shell reads `GET /api/v1/tenant/packs` and renders only enabled packs. Core ships no industry routes. |
| Migrations | `ar_domain.packs.alembic_env(pack_id, schema)` and version table `{schema}_alembic_version`. Pack tables are not in the core schema. |
| Enablement | `tenant_pack_flags`. Disabled pack routes, tools, and nav return 404. Data stays. |
| Testing kit | `ar_testing.packs.install_fixture(pack_id)` installs a signed fixture manifest against a test database, runs that pack's Alembic, and asserts core `alembic heads` is still one head. Connector conformance stays in the connector SDK. |

A pack calls core services. Core never imports a pack.
