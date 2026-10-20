# Scope and non-goals

## In scope for v1 (milestones M0–M15, see [plan](../09-plan/README.md))

The GRC solution pack (M16–M19) is in the repository and is not required to call 1.0 shipped. Core 1.0 includes the generic assurance tasks in M3, M5, M7, M13 and M14.

| Area | PRD | Highlights |
|---|---|---|
| Agent builder | [01](../01-prd/01-agent-builder.md) | Declarative agents, versions, publish/rollback, test chat, bundles import/export, draft from description |
| Tools & connectors | [02](../01-prd/02-tool-registry.md) | Remote MCP servers, OpenAPI-to-MCP, SQL connector, built-in servers, review, risk classes, OAuth connections |
| Knowledge | [03](../01-prd/03-knowledge.md) | Collections, sources (upload, web, SharePoint, Confluence, Google Drive, S3), hybrid retrieval with ACLs, citations |
| Chat | [04](../01-prd/04-chat.md) | Streaming chat, files, citations, regenerate/edit, sharing, export, feedback |
| Runs & subagents | [05](../01-prd/05-runs-subagents.md) | Durable runs, planning, cancel, budgets, subagent delegation, API runs with callbacks |
| Sandboxes & browser | [06](../01-prd/06-sandboxes.md) | Code execution, packages, file outputs, headless browser, egress allowlists |
| Memory | [07](../01-prd/07-memory.md) | User/agent/team memory, extraction, review, context compaction |
| Routines | [08](../01-prd/08-routines.md) | Schedules, webhooks, internal events, polling, delivery to channels/email |
| Skills | [09](../01-prd/09-skills.md) | Versioned instruction + asset packages loaded on demand |
| Policies & approvals | [10](../01-prd/10-approvals.md) | OPA policies, risk defaults, approvals in web/Slack/Teams, standing approvals, simulation |
| Channels | [11](../01-prd/11-channels.md) | Web, Slack, Teams, email notifications, REST API, OpenAI-compatible endpoint, embeddable widget for signed-in users |
| Admin, tenancy, billing | [12](../01-prd/12-admin-tenancy-billing.md) | Tenants, users, teams, roles, SSO/SCIM, secrets, usage, quotas, audit, retention, DPDP rights |
| Observability | [13](../01-prd/13-observability.md) | Traces, metrics, logs, dashboards, alerts, run inspector |
| Evaluation | [14](../01-prd/14-evaluation.md) | Suites, cases, judges, regression gates on publish |
| Records and assurance | [15](../01-prd/15-records-governance.md) | Immutable evidence, sign-off, segregation of duties, strict grounding, run records, legal hold, external participants, binders, pack hooks |
| GRC pack (after 1.0) | [10-grc-pack](../10-grc-pack/prd.md) | Frameworks, collectors, workflows, auditor portal. Not core |

## Non-goals (v1)

- **Training foundation models.** Open-weight models are consumed; fine-tuning (LoRA) is later.
- **Replacing systems of record.** Agents act through existing APIs.
- **Fully autonomous high-risk actions.** W3 actions always need a per-call human approval; standing approvals never apply to W3.
- **Public anonymous chatbot.** Only authenticated employees and approved service accounts. The widget requires a signed-in user or a service-account-minted session for a known user ([OQ](../open-questions.md)). External participants are a scoped exception: guest principals reach portals only, not chat ([OQ-26](../open-questions.md)).
- **Frontier-parity guarantees.**
- **Visual low-code workflow builder.** Routines are natural language + configuration.
- **Third-party model APIs.** `model-gateway` can only call providers the operator registers; SaaS operators are expected to register company-hosted endpoints only.
- **Mobile native apps.** Responsive web only.
- **Real-time voice.**
- **Marketplace of public tools/agents.** Bundles are exchanged as files only.
- **Kafka or other brokers.** Outbox + Valkey + Temporal suffice for v1 ([open-questions](../open-questions.md)).
- **Multi-currency invoicing.** Usage is metered in micro-units of a single tenant-configured currency; no invoicing engine.
