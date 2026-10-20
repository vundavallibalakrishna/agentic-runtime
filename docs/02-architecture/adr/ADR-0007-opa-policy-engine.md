# ADR-0007: OPA for tool-call policy with data-driven tenant rules; RBAC in Python

- Status: Accepted
- Date: 2026-10-20

## Context

Tenants need expressive, testable rules (by tool, risk, agent, user attributes, arguments, time) evaluated on every tool call, with explainable reasons and simulation.

## Decision

Run OPA as a sidecar-free service (`opa` deployable). One platform Rego entrypoint (`policies/rego/ar/policy.rego`) evaluates tenant rules expressed in a JSON rule DSL ([definition-schema §7](../../05-contracts/definition-schema.md#7-policy-kind-policy)) shipped as bundle data from `api`; optional custom Rego per tenant can only tighten. RBAC permission checks for API endpoints stay in Python (simple set membership, hot path).

## Consequences

Tenants never write Rego unless enabled; rules are versioned, tested and simulated; OPA is fast and auditable. Cost: bundle propagation delay ≤ 15 s (kill switches are separate and immediate).

## Alternatives considered

Cedar (good fit but smaller ecosystem in Python/k8s tooling at the time of writing); pure Python rules engine (rejected: harder to test independently, no standard bundle distribution).
