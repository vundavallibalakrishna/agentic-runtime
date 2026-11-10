# ADR-0028: Agnostic core

- Status: Accepted
- Date: 2026-11-10

## Context

Principle 3 said the evidence vault, sign-off, legal hold, retention, the AI register, external participants, and binders were generic and therefore stayed in core. That kept a records product, and the words of particular buyers, on the platform every customer runs. Four-eyes approval and the security audit log are different: they are controls on any tool call and any state change, and they do not name an industry.

## Decision

Core is domain-agnostic. Nothing specific to an industry lives in core code, schemas, seeds, tools, prompts, tests, UI, or product docs.

Records-as-a-product moves to an optional signed pack. That product is the evidence vault, legal holds, binders, the AI register, guest packets, and the questionnaire product. Core does not ship it, seed it, or name it.

Four-eyes (segregation of duties on a tool call) and the security audit log stay in core. They are generic.

This replaces principle 3 of [AGENTS.md](../../../AGENTS.md). It supersedes, for placement in core, [ADR-0021](ADR-0021-evidence-immutability.md) and [ADR-0024](ADR-0024-guest-principals.md), and the 2026-11-05 decision that assurance stays in core behind `features.assurance`. The removal is [Stage 2](../../09-plan/agnostic-production-plan.md).

## Consequences

A tenant with no pack installed has agents, tools, files, approvals, and an audit log. It does not have an evidence desk. A later pack may reuse the immutability rules of ADR-0021 inside its own schema. Core migrations stop writing the records tables, then drop them (expand/contract).

## Alternatives

Keep the records product in core behind a flag. Rejected: a flag still ships the schema, permissions, tools, and routes to every customer. Rename the records nouns and leave them in core. Rejected: the product is still a records suite, only with different words.
