# Vision

**Agentic Runtime** is a self-hosted platform on which a company builds, governs and operates AI agents for its employees, running entirely on the company's own infrastructure and models. The design follows `docs/architecture/agentic-runtime-architecture.(docx|pdf)` (the reference architecture, not duplicated here).

## Problem

Employees want assistants that *do work*: query systems, analyse data, draft documents, file tickets, watch for events. Companies cannot send their data to third-party model APIs, cannot give an AI agent broader permissions than the person using it, and need every action to be reviewable. Building all of this per use case wastes effort and multiplies risk.

## Product in one paragraph

Builders define **agents** (persona, instructions, model alias, tools, knowledge, memory, policies, skills, channels, sandbox) declaratively. Tool owners register **tools** (MCP servers, internal APIs, databases) once, with risk classes and review. Admins set **policies** and **approvals**. Employees chat with agents on the **web app**, in **Slack** or **Teams**, or through the **API**. Agents plan, call tools, run code in **sandboxes**, browse, produce **files**, recall **memory**, delegate to **subagents**, follow **skills** and run unattended **routines** on schedules and events. Everything is durable, audited, metered and evaluated.

## Goals (from the reference architecture)

| # | Goal | Measured by |
|---|---|---|
| G1 | Full data sovereignty | Zero outbound calls to third-party model APIs; egress policy + audit ([threat-model](../06-security/threat-model.md)) |
| G2 | Useful agents, not only chat | Task success rate in eval suites ([eval-strategy](../08-quality/eval-strategy.md)) |
| G3 | Secure by construction | Agents never exceed the acting user's permissions; risky writes need approval; all actions audited ([authn-authz](../06-security/authn-authz.md)) |
| G4 | Grounded in company knowledge | Citations present; ACL leak tests pass ([spec 10](../03-specs/10-knowledge.md)) |
| G5 | Extensible platform | Tools, agents, routines added self-service with review, no platform change ([spec 08](../03-specs/08-tool-registry-mcp.md)) |
| G6 | Operable at enterprise scale | Multi-tenant, HA, DR, observable, cost per team ([07-ops](../07-ops/scaling.md)) |
| G7 | Model agility | Models swapped behind aliases without agent changes ([spec 04](../03-specs/04-model-gateway.md)) |

## Guiding principles

1. **Least privilege, delegated identity** — the agent is the user's assistant, never a privileged service account.
2. **Model output is a proposal; tool output is data** — neither authorises anything ([prompt-injection](../06-security/prompt-injection.md)).
3. **Everything durable** — anything that can outlive a request runs in a Temporal workflow ([ADR-0003](../02-architecture/adr/ADR-0003-temporal-durable-runs.md)).
4. **Standard interfaces** — OpenAI-compatible inference, MCP for tools, OIDC for identity, OpenTelemetry, S3 API.
5. **Measure before you scale** — every prompt, model or tool change runs through evaluation.
6. **One codebase, two deployment modes** — multi-tenant SaaS and single-tenant on-prem ([deployment-modes](deployment-modes.md)).

## Related

[glossary](glossary.md) · [personas](personas.md) · [scope](scope.md) · [PRD](../01-prd/README.md) · [plan](../09-plan/README.md)
