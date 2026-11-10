# ADR-0023: Solution packs use public extension points and a separate Alembic history

- Status: Accepted. Refined by [ADR-0034](ADR-0034-signed-pack-model.md) (2026-11-10): a pack is out of process, the manifest is signed, and an unsigned pack is refused outside development.
- Date: 2026-10-20

## Context

An industry domain must not fork core and must not add tables to the core linear migration history. Later packs need the same boundary. The pack that first used this boundary was removed in M30.

## Decision

A pack is a content pack ([spec 05 §10](../../03-specs/05-agent-registry.md#10-content-packs)) plus an `extension` block. Core exposes six hooks only: an HTTP mount at `/api/v1/ext/{pack_id}`, a pack Alembic environment with its own version table, permission registration, audit-action registration, a web nav slot, and a per-tenant enable flag. Core modules must not import `ar_pack_*`. Pack schema migrations are not revisions in the core history ([OQ-28](../../open-questions.md)). No pack ships in this tree. Core revision `0031` drops a retired pack schema when that schema is already present. Normative behaviour: [spec 21 §6](../../03-specs/21-records-governance.md#6-pack-extension-points).

## Consequences

Pack upgrades run the pack's Alembic upgrade, then re-import declarative resources. Uninstall disables the pack and keeps data unless the operator passes `drop_schema` with step-up. Core 1.0 ships the hooks (M14-T13) before any pack milestone starts.

## Alternatives considered

A single Alembic history that includes pack tables (rejected: a pack upgrade would be a core release, and a second pack would entangle unrelated schemas). Loading pack code into core services by monkey-patching private modules (rejected: that is a fork).
