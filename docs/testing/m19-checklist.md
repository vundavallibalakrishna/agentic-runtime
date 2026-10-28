# M19 visual checklist

Sign in as the dev admin. The GRC pack is installed for the dev tenant. Audit seed data is already there: PBC request “SOC 2 population extract”, business rule “Pay and approve”, entitlements for ada@example.com, a draft “Quarterly access review”, an announced SEBI inspection, an access DSAR, consent for customer-1842, a passing BCP test, and model asset “Support assistant”.

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

`make migrate` stays the core history. Pack revision `0002` adds inspections, DSAR, consent and resilience tables. HTTP rows stay on the process store (OQ-52).

Earlier screens stay on Chat, Agents, Tools, Knowledge, Memory, Skills, Routines, Channels, Approvals, Runs, Models, Computers, Users, Usage, Quotas, Evaluations, Platform health, Assurance, and the M16, M17 and M18 GRC pages.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading and a **GRC** item in the sidebar.
2. Open **GRC**, then **Audit**. Expect six cards: Requests, Reviews, Reports, Inspections, Privacy and Resilience. Each card shows a count.
3. Open **Requests**. Expect “SOC 2 population extract”, status open.
4. Open **Reviews**. Expect “Quarterly access review” as draft, the rule “Pay and approve”, and ada@example.com with pay and approve. Choose **Start campaign**. Expect “Campaign started.” and a Conflict on ada@example.com.
5. Open **Reports**. Choose **Render Statement of applicability**. Expect a binder id and status ready. Choose **Render Board pack**. Expect “A signed review is still required.”
6. Open **Inspections**. Expect SEBI, status announced.
7. Open **Privacy**. Expect an access request and customer-1842, purpose Account notices, state granted.
8. Open **Resilience**. Expect bcp pass and “Support assistant”, tier high.
9. Open `/guest/portal` without a guest session. Expect the heading “Auditor room” and **Request a guest link**.
10. Narrow to 375px and switch to dark. The same tokens stay. Empty and error states use the shared empty panel and the alert role.

Playwright walks the same path:

```bash
cd apps/web && E2E_SCREENSHOT_DIR=../../docs/testing/m19 pnpm exec playwright test e2e/m19-audit.spec.ts
```

Screenshots land in `docs/testing/m19/` for light and dark, desktop (1280) and mobile (375). The walkthrough video is `docs/testing/m19/walkthrough.webm`.
