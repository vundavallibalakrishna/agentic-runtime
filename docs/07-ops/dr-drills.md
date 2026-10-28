# DR drills

| Date | Kind | Result |
|---|---|---|
| 2026-10-28 | Fixture restore (`scripts/dr/restore_drill.sh`) | Chain verifies, row counts present, WAL archive interval 300 s (inside the 15 minute RPO). Elapsed time is seconds, inside the 4 hour RTO. Knowledge vectors are rows in the Postgres dataset, not a separate Qdrant snapshot. |

A live drill restores the CloudNativePG backup into namespace `ar-dr-drill` with `scripts/dr/restore_drill.sh` pointed at `DR_DATASET` from the backup, then `scripts/dr/export_tenant.py` for one SaaS tenant and `scripts/dr/reconcile_temporal.py` for runs that exist only in Temporal. That cluster drill is an operator step (OQ-48).
