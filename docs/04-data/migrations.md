# Migration strategy

## 1. Tooling

- Alembic lives in `libs/ar_domain/src/ar_domain/migrations/` with `env.py` configured for async SQLAlchemy and `target_metadata = ar_domain.db.Base.metadata`.
- Revision ids are timestamp-prefixed and human-named: `20261101_0001_identity_core.py`. Configure `file_template = %%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s` and use sequential 4-digit `rev` values (`--rev-id 0001`).
- One linear history (no branches). CI fails if `alembic heads` returns more than one head.
- Migrations run as the `ar_owner` role in the `migrate` Kubernetes Job (Helm `pre-install,pre-upgrade` hook) or `make migrate` locally.

## 2. Rules (never skip)

1. Every change to a SQLAlchemy model ships with a migration in the same PR. CI runs `alembic check` (autogenerate diff must be empty after `upgrade head`).
2. Every new tenant-owned table includes the RLS statements from [rls.md](rls.md) §3 in the same migration, and the `set_updated_at` trigger if it has `updated_at`. Use the helpers `ar_domain.migrations.helpers.enable_tenant_rls(op, table)` and `add_updated_at_trigger(op, table)`.
3. Migrations must be **backward compatible with the previous release** (expand/contract) because pods roll gradually:
   - Expand: add nullable columns or columns with defaults; add tables; add indexes `CONCURRENTLY` (in a separate migration with `transaction_per_migration` and `op.execute("COMMIT")` guard, or with `with op.get_context().autocommit_block()`).
   - Migrate data: a Temporal maintenance workflow or batched migration (≤ 5,000 rows per batch) for large tables, never a single giant `UPDATE`.
   - Contract: drop columns or tighten constraints only in a later release after code no longer uses them.
4. `NOT NULL` on existing large tables: add `CHECK (...) NOT VALID`, then `VALIDATE CONSTRAINT`, then `SET NOT NULL`.
5. Downgrades are written for every migration but are only used in development; production rolls forward.
6. No migration may call external services or depend on application settings other than the DSN.
7. Seed data (system roles, plans, platform built-in tool servers, platform sandbox templates) is applied by `ar_domain.seed.apply()` in the `migrate` job after `upgrade head`; it is idempotent (upserts by natural key).

## 3. Initial revision plan

| Rev | Name | Content | Plan task |
|---|---|---|---|
| 0001 | `extensions_and_helpers` | extensions, `set_updated_at()`, `app_tenant_id()`, role grants | M1-T02 |
| 0002 | `identity_core` | §1 tables | M1-T03 |
| 0003 | `audit_events` | §15 `audit_events` + append-only trigger | M1-T05 |
| 0004 | `events_core` | §17 tables | M1-T06 |
| 0005 | `secrets` | §2 tables + `fk_idp_secret` | M1-T07 |
| 0006 | `models` | §3 tables | M2-T01 |
| 0007 | `usage` | §15 `usage_events`, `usage_daily`, `quotas` | M2-T02 |
| 0008 | `agents` | §4 tables | M2-T05 |
| 0009 | `conversations_runs` | §5 tables | M2-T06 |
| 0010 | `files` | §11 table + `fk_agents_avatar` | M2-T07 |
| 0011 | `tools` | §6 tables + `fk_tool_calls_result` | M4-T01 |
| 0012 | `policy_approvals` | §7 tables + `fk_tool_calls_approval` | M5-T01 |
| 0013 | `sandboxes` | §10 tables + `fk_sandboxes_snapshot` | M6-T01 |
| 0014 | `knowledge` | §8 tables (incl. `chunk_embeddings`, its RLS policy, the GIN `tsv`/`acl` indexes and the five per-dimension partial HNSW indexes) + `fk_documents_raw`, `fk_documents_parsed` | M7-T01 |
| 0015 | `memory` | §9 table | M8-T01 |
| 0016 | `skills` | §12 tables | M9-T02 |
| 0017 | `routines` | §13 tables + `fk_runs_routine`, `fk_sa_routine` | M10-T01 |
| 0018 | `channels` | §14 tables | M11-T01 |
| 0019 | `evals` | §16 tables | M13-T03 |
| 0020 | `content_packs` | §20 tables | M3-T09 |
| 0021 | `reviews_signoffs` | §21 tables | M5-T08 |
| 0022 | `sod_constraints` | §21 `sod_constraints` (split so M5-T09 owns the constraint seed) | M5-T09 |
| 0023 | `run_records` | §22 tables, without the evidence FK | M13-T07 |
| 0024 | `evidence_vault` | §23 tables + `fk_run_records_evidence` | M14-T08 |
| 0025 | `legal_hold_retention` | §24 tables and the retention seed | M14-T09 |
| 0026 | `ai_governance` | §25 tables | M14-T10 |
| 0027 | `guest_principals` | §26 tables + `fk_guest_totp_secret` | M14-T11 |
| 0028 | `binder_exports` | §27 table | M14-T12 |
| 0029 | `pack_extension` | §28 tables | M14-T13 |

Deferred foreign keys that reference tables created in later revisions are added in the later revision (listed in the Content column above). Revision 0022 only creates `sod_constraints`; `review_queues`, `review_items` and `signoffs` are revision 0021. M5-T09 depends on 0021 and adds 0022.

## 4. Partitioning roadmap

v1 tables are unpartitioned. When `messages`, `run_events`, `usage_events` or `audit_events` exceed ~200 M rows, convert to monthly range partitions on `created_at`/`occurred_at` using a new table + backfill + swap (documented runbook in [07-ops/runbooks.md](../07-ops/runbooks.md#rb-12-partition-a-large-table)). See [open-questions](../open-questions.md) OQ-07.

## 5. Testing migrations

- `tests/integration/test_migrations.py`: upgrade from empty to head, downgrade to base, upgrade again (dev DB container).
- `test_models_match_schema`: after `upgrade head`, `alembic check` reports no diff.
- RLS tests from [rls.md](rls.md) §5.

## 6. Pack schemas

Core history stays a single line (revisions 0001–0029 and anything added after). A solution pack does not append to that line. Each pack ships its own Alembic environment created with `ar_domain.packs.alembic_env` ([spec 21 §6](../03-specs/21-records-governance.md#6-pack-extension-points), [ADR-0023](../02-architecture/adr/ADR-0023-pack-extensions.md), [OQ-28](../open-questions.md)). The GRC pack uses Postgres schema `grc` and version table `grc_alembic_version`. Pack upgrades run `alembic upgrade head` in that environment before content-pack resource import. `alembic heads` for the core environment must still return one head; pack environments are checked separately (`alembic -c packs/grc/alembic.ini heads`).
