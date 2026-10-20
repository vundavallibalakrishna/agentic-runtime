# ADR-0014: S3-compatible object storage; SeaweedFS as the bundled default

- Status: Accepted
- Date: 2026-10-20

## Context

Files, artifacts, snapshots, parsed documents and exports need cheap durable storage on-prem and in cloud.

## Decision

Use the S3 API exclusively (`aiobotocore`/`boto3`). Bundle SeaweedFS for installs without existing storage; any S3-compatible service (cloud or on-prem) can be configured ([spec 13](../../03-specs/13-files-artifacts.md)). The previously common community MinIO distribution is not used because its community edition was archived in 2026.

## Consequences

Portable storage layer. Cost: presigned-URL reachability must be configured (`AR_S3_PUBLIC_ENDPOINT`) or downloads proxied.

## Alternatives considered

Postgres large objects (rejected: DB bloat); filesystem volumes (rejected: no multi-node).
