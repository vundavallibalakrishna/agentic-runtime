# ADR-0018: Declarative, versioned YAML/JSON definitions for agents and other resources

- Status: Accepted
- Date: 2026-10-20

## Context

Companies want agents-as-code (review in Git, promote between environments) as well as a UI builder.

## Decision

Every configurable resource has a definition schema (`apiVersion: agentic-runtime.dev/v1`, `kind`, `metadata`, `spec`) ([definition-schema](../../05-contracts/definition-schema.md)); the UI edits the same structure; bundles import/export idempotently; published versions are immutable with references resolved at publish time.

## Consequences

GitOps-friendly, reproducible runs. Cost: schema versioning discipline.

## Alternatives considered

UI-only configuration (rejected: no review/promotion).
