# Product requirements (PRD)

User stories for the 14 product areas of v1. Personas: [personas](../00-overview/personas.md). Scope and non-goals: [scope](../00-overview/scope.md). Terms: [glossary](../00-overview/glossary.md).

## Format

Each story: **ID** (`US-<AREA>-<nn>`, stable, never renumbered), persona, story, **acceptance criteria** (testable, Given/When/Then or bullet rules), **Spec** (the normative behaviour; the spec wins on detail), **Plan** (tasks that deliver it). Priority: **P0** = required for 1.0, **P1** = required for 1.0 but may slip to a 1.x minor with product sign-off.

## Areas

| # | File | Area | Prefix | Stories |
|---|---|---|---|---|
| 01 | [01-agent-builder.md](01-agent-builder.md) | Agent builder | `US-AGT` | 10 |
| 02 | [02-tool-registry.md](02-tool-registry.md) | Tools & connectors | `US-TOOL` | 10 |
| 03 | [03-knowledge.md](03-knowledge.md) | Knowledge | `US-KN` | 8 |
| 04 | [04-chat.md](04-chat.md) | Chat | `US-CHAT` | 9 |
| 05 | [05-runs-subagents.md](05-runs-subagents.md) | Runs & subagents | `US-RUN` | 8 |
| 06 | [06-sandboxes.md](06-sandboxes.md) | Sandboxes & browser | `US-SBX` | 7 |
| 07 | [07-memory.md](07-memory.md) | Memory | `US-MEM` | 6 |
| 08 | [08-routines.md](08-routines.md) | Routines | `US-RTN` | 7 |
| 09 | [09-skills.md](09-skills.md) | Skills | `US-SKL` | 5 |
| 10 | [10-approvals.md](10-approvals.md) | Policies & approvals | `US-APR` | 8 |
| 11 | [11-channels.md](11-channels.md) | Channels | `US-CH` | 8 |
| 12 | [12-admin-tenancy-billing.md](12-admin-tenancy-billing.md) | Admin, tenancy, billing | `US-ADM` | 14 |
| 13 | [13-observability.md](13-observability.md) | Observability | `US-OBS` | 6 |
| 14 | [14-evaluation.md](14-evaluation.md) | Evaluation | `US-EVAL` | 6 |

## Cross-cutting acceptance criteria (apply to every story)

1. **Tenant isolation**: no story's data is visible across tenants; cross-tenant access returns 404 ([tenancy-isolation](../02-architecture/tenancy-isolation.md)).
2. **Authorisation**: every action checks the permission named in its spec ([authn-authz §3](../06-security/authn-authz.md#3-permission-catalogue)); UI hides actions the user cannot perform.
3. **Audit**: every state change writes the audit action listed in [audit §3](../06-security/audit.md#3-catalogue).
4. **Accessibility**: WCAG 2.1 AA for every screen ([coding-standards-typescript §4](../08-quality/coding-standards-typescript.md#4-accessibility-and-i18n)).
5. **Performance**: within [performance-budgets](../08-quality/performance-budgets.md).
6. **Both deployment modes**: works in `saas` and `single_tenant` unless the story says otherwise ([deployment-modes](../00-overview/deployment-modes.md)).
7. **API parity**: everything the web app does is available through the public API ([api-catalogue](../05-contracts/api-catalogue.md)).
