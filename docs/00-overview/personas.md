# Personas

Each persona maps to one or more system roles ([authn-authz §4](../06-security/authn-authz.md#4-system-roles)). PRD stories name the persona in "As a …".

| Persona | System role(s) | Goals | Primary surfaces |
|---|---|---|---|
| **Employee (end user)** — "Priya, finance analyst" | `member` | Ask questions grounded in company docs, get analyses and files, automate recurring reports, approve own agents' actions | Web chat, Slack/Teams, email deliveries |
| **Agent builder** — "Arjun, team automation lead" | `builder` (team or tenant scope) | Create and iterate on agents, attach tools/knowledge/skills, test, evaluate, publish | Agent builder, test chat, eval pages |
| **Tool owner** — "Meera, platform engineer for the ticketing system" | `tool_owner` | Register MCP servers / APIs / databases, set risk classes, maintain versions, see usage and errors | Tools pages, tool test console |
| **Knowledge manager** — "Rahul, HR content owner" | `knowledge_manager` | Connect sources, keep collections fresh, control access and sensitivity | Knowledge pages |
| **Approver** — "Sunita, finance manager" | `approver` (often team scope) | Decide approvals quickly with full context; grant standing approvals for routine work | Approvals inbox, Slack/Teams cards, email |
| **Tenant administrator** — "Vikram, IT admin" | `tenant_admin` | Configure SSO/SCIM, users, teams, roles, models, policies, channels, quotas, retention; respond to incidents | Admin area |
| **Auditor / security** — "Anita, CISO office" | `auditor` | Review audit trail, verify chain integrity, export to SIEM, review policies and approvals | Audit, policies (read-only), observability |
| **Developer / integrator** — "Kiran, internal app developer" | service account with API keys; `builder` for their agents | Call agents from apps via REST/OpenAI-compatible API, receive callbacks/webhooks, embed widget | API, webhooks, widget |
| **Platform operator** — "Ops team" (SaaS operator or on-prem install owner) | Keycloak realm role `platform_admin` (SaaS) / Helm operator (on-prem) | Provision tenants, register model providers, monitor health and capacity, upgrade, back up | Platform admin pages, Grafana, Helm |
| **External participant** — invited reviewer | guest principal (`external` or `partner`) | See only the records in the grant, for a limited time | Guest portal |
| **Control owner** (GRC pack) | pack permissions such as `grc.controls:manage` | Keep controls, evidence and findings current | `/grc` when the pack is enabled |

## Persona-driven design constraints

1. Employees never see configuration complexity: a default agent `assistant` exists in every tenant ([spec 02 §4](../03-specs/02-identity-tenancy.md)).
2. Approvers must be able to decide from Slack/Teams/email without opening the web app, but W3 decisions require web step-up ([spec 09](../03-specs/09-policy-approvals.md)).
3. Builders can iterate without affecting users: drafts and test chat are isolated from published versions.
4. Auditors are read-only everywhere and can never read conversation content unless `conversations:read_all` is explicitly granted.
5. Platform operators in SaaS mode cannot read tenant content without a time-boxed support-access grant ([authn-authz §6](../06-security/authn-authz.md#6-support-access-saas)).
