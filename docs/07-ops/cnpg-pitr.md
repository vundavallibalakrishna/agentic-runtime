# CloudNativePG point-in-time recovery

Proof label: `contract`. `scripts/cnpg_pitr_kind.sh` installs the CloudNativePG operator and MinIO on kind, writes a row, takes a base backup, writes a second row, and restores to a timestamp between the two writes. The host does not publish port 5432. The job runs when those files change and on the nightly workflow. It is not `live`.

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

```bash
bash scripts/cnpg_pitr_kind.sh
```

The script creates a kind cluster when kubectl has no current cluster. It then:

1. Installs CloudNativePG 1.30.1.
2. Builds MinIO from the official `RELEASE.2025-09-07T16-13-09Z` binary (Docker Hub no longer publishes `minio/minio`) and creates the `ar-backup` bucket. Barman is told `--addressing-style path` through the 1.30 command-arg fields. The 1.30.1 CRD does not have `s3AddressingStyle`.
3. Creates cluster `ar-src` with WAL archiving to that bucket.
4. Inserts `before`, takes a base backup, records the clock, then inserts `after`.
5. Restores cluster `ar-restored` to the recorded timestamp.
6. Asserts `before` is present and `after` is not.

`scripts/dr/pitr_contract.py` remains the logical restore a laptop can run without kind. It is not a WAL replay.
