# CloudNativePG point-in-time recovery

Proof label: `contract` for the restore check in this repository. A restore on a running CloudNativePG cluster is an operator step and is not claimed as `live` here.

## What the cluster already does

The chart's CloudNativePG cluster archives WAL (`archive_timeout` is 300 seconds). A base backup is the object-store backup the chart's backup cron writes. Point-in-time recovery replays that WAL up to a timestamp.

## Restore

1. Pick the timestamp from a known-good moment. Use UTC.
2. Create a new cluster that recovers into a new instance. Do not point the API at the new instance until the check below passes.

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: agentic-runtime-pitr
spec:
  instances: 1
  bootstrap:
    recovery:
      source: agentic-runtime
      recoveryTarget:
        targetTime: "2026-11-10T12:00:00Z"
  externalClusters:
    - name: agentic-runtime
      barmanObjectStore:
        destinationPath: s3://agentic-runtime-backup/postgres
        wal:
          compression: gzip
```

3. When the new cluster is ready, run the contract check against it. The check inserts nothing. It reads a marker row that existed before `targetTime` and asserts a row written after `targetTime` is absent.

```bash
AR_DATABASE_URL=postgresql://ar_owner@127.0.0.1:5433/agentic_runtime \
  uv run python scripts/dr/pitr_contract.py --check
```

The host port is 5433. Do not use 5432.

4. Cut the API over only after that check passes. Keep the old cluster until the next successful backup.

## Contract test

`scripts/dr/pitr_contract.py` can also run against a local Postgres. It creates a scratch table, copies the rows out, deletes them, restores the copy, and asserts the marker is back. That is a logical restore, not a WAL replay. It is the contract the operator check reuses: a marker from before the target is present, and a marker from after the target is not.
