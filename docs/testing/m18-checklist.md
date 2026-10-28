# M18 visual checklist

Sign in as the dev admin. The GRC pack is installed for the dev tenant. Workflow seed data is already there: an approved library answer, a questionnaire whose export is still blocked, vendor Northwind, a draft access-control policy, risk Vendor outage scored 12, a DPDP circular, a laptop incident on a 72 hour DPDP clock, a proposed waiver, and a restricted ethics case.

Seed data is the dev tenant. The admin is `admin@dev.local`. `fake-llm` answers chat. No model API key.

## Start

```bash
make bootstrap
make migrate
uv run alembic -c packs/grc/alembic.ini upgrade head
make seed
make dev
```

Web: http://localhost:3000. API: http://localhost:8000. Dev login: **Sign in as admin@dev.local** on `/login`.

Host ports come from `.env`. `make ports-check` names a busy port. `make dev AUTO_PORTS=1` moves it. Do not stop Postgres, Temporal, Redis, or the apps already listening on 8000, 8001 and 8013. Point `AR_PORT` and `AR_WEB_HOST_PORT` at free ports instead.

`make migrate` stays the core history. The pack command creates schema `grc` and does not move it past revision `0001`. HTTP rows for these workflows stay on the process store (OQ-49, OQ-50, OQ-51).

Earlier screens stay on Chat, Agents, Tools, Knowledge, Memory, Skills, Routines, Channels, Approvals, Runs, Models, Computers, Users, Usage, Quotas, Evaluations, Platform health, Assurance, and the M16 and M17 GRC pages.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading and a **GRC** item in the sidebar.
2. Open **GRC**, then **Workflows**. Expect eight cards: Questionnaires, Vendors, Policies, Risks, Regulatory, Incidents, Exceptions and Ethics. Each card shows a count.
3. Open **Questionnaires**. Expect “Do you encrypt disks?” as approved and a draft for the backup-site question. Choose **Export questionnaire**. Expect “A signed review is still required.”
4. Open **Vendors**. Expect Northwind, still unscored, from a document review.
5. Open **Policies**. Expect Access control as a draft. Choose **Publish policy**. Expect the same signed-review message. The acknowledgement campaign is created only after publish.
6. Open **Risks**. Expect Vendor outage, status open, score 12.
7. Open **Regulatory**. Expect the DPDP circular, status new.
8. Open **Incidents**. Expect “Laptop with customer extracts” and `dpdp 72h`.
9. Open **Exceptions**. Expect “The legacy store is isolated until the quarter closes.” and status proposed.
10. Open **Ethics**. Expect “Unsolicited gift from a supplier”, status open.
11. Narrow to 375px and switch to dark. The same tokens stay. Empty and error states use the shared empty panel and the alert role.

## Deferred

Campaign start, close and item decisions are M19-T03. PBC, entitlements, report templates, inspections, DSAR and resilience are M19. Breach clocks record a Temporal timer start and do not add a worker (OQ-51). Schema `grc` is not revised in this milestone.
