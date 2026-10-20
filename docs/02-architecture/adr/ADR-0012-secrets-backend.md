# ADR-0012: OpenBao/Vault for secrets with an envelope-encrypted DB fallback

- Status: Accepted
- Date: 2026-10-20

## Context

Tenant credentials (API keys, DSNs, OAuth refresh tokens) must never be stored in plaintext or exposed to models/sandboxes.

## Decision

`SecretStore` abstraction with `vault` (OpenBao or Vault KV v2, Kubernetes auth) and `db_encrypted` (AES-256-GCM envelope encryption with KEKs from `AR_DB_ENCRYPTION_KEYS`) backends ([spec 03](../../03-specs/03-secrets-credentials.md)).

## Consequences

Strong default for production, simple fallback for small installs and local dev. Cost: two code paths (shared conformance tests).

## Alternatives considered

Kubernetes Secrets only (rejected: per-tenant dynamic secrets, no audit); cloud KMS-only (rejected: on-prem).
