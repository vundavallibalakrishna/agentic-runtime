# ADR-0015: Approvals bound to an RFC 8785 (JCS) hash of tool version + arguments

- Status: Accepted
- Date: 2026-10-20

## Context

An approval must authorise exactly what the approver saw; the model or an attacker must not be able to change arguments after approval (TOCTOU).

## Decision

`args_hash = sha256(JCS({tool_version_id, arguments}))`. The approver submits the hash they saw; `mcp-gateway` re-verifies the hash and single-use (`consumed_at`) before execution ([spec 09](../../03-specs/09-policy-approvals.md)).

## Consequences

Tamper-evident, cross-language reproducible hashes. Cost: canonicalisation library dependency (`rfc8785`).

## Alternatives considered

Approving by tool-call id only (rejected: arguments could be swapped by a compromised component).
