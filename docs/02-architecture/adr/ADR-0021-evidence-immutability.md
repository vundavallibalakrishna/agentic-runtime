# ADR-0021: Evidence objects are immutable, hashed, signed and locked

- Status: Accepted
- Date: 2026-10-20

## Context

Auditors and GRC buyers need to show that a captured record was not altered after collection. The audit log is hash-chained but stores no content. Files support retention, and the audit archive bucket uses Object Lock, but neither is an evidence object with provenance and a verification API.

## Decision

Evidence bytes live in a dedicated Object Lock bucket. Each item stores SHA-256 of the bytes, an Ed25519 signature by the records service over a canonical manifest, and an optional RFC 3161 timestamp. Content columns cannot be updated. Object Lock retention is applied at capture and is never shortened. Timestamping is off unless the tenant turns it on ([OQ-25](../../open-questions.md)). Verification is an explicit API, not a side effect of download. Normative behaviour: [spec 21 §1](../../03-specs/21-records-governance.md#1-evidence-vault).

## Consequences

Captures are heavier than ordinary file uploads (hash, signature, lock, custody row, audit). The evidence bucket is a second object store prefix with its own lifecycle. Guests never receive the original bytes of PDF or image evidence without a watermark, and the original object stays untouched.

## Alternatives considered

Storing evidence as `files` rows with a flag (rejected: file lifecycle allows delete and replace, and mixes user uploads with assurance records). Hash-chaining evidence rows the way audit events are chained (rejected: the audit chain already covers the custody actions; content integrity is a hash of the bytes plus a signature, which an offline verifier can check without the chain database).
