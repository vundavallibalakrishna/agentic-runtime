# M12 visual checklist

Usage and quotas are visible to an admin. A daily token quota of 0 blocks the next chat with a clear message. The seeded week of usage exports as CSV and matches the daily totals.

Seed data is the dev tenant (`billing_currency` INR, timezone Asia/Kolkata, plan `self_hosted`). The admin has a personal token quota of 100,000 per day. Seven days of model usage are recorded. Today's bar is 36,000 tokens, under the warn line. Chat stays open until a tighter quota is saved.

## Start

```bash
make bootstrap
make dev
make seed
```

Web: http://localhost:3000. API: http://localhost:8000. Dev login: **Sign in as admin@dev.local** on `/login` (`POST /api/v1/auth/dev-login`). No model API key. `fake-llm` answers chat.

Host ports come from `.env`. `make ports-check` names a busy port. `make dev AUTO_PORTS=1` moves it. Defaults: Postgres 5432, Valkey 6379, Temporal 7233, API 8000, web 3000.

Earlier screens stay where they were: Chat, Agents, Tools, Knowledge, Memory, Skills, Routines, Channels, Approvals, Runs, Models, Computers, Users. Their checklists are `docs/testing/m2.5-checklist.md` through `docs/testing/m11-checklist.md`.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading.
2. Open **Usage** (`/admin/usage`). Expect a total, a bar chart, and **Export CSV**. A range with no rows shows "No usage in this range."
3. Change **Group by** to agent. Expect the assistant row. A failed load shows **Try again**.
4. Open **Quotas** (`/admin/quotas`). Expect the model token quota, a consumption bar, and **Dev Admin**. An empty tenant shows "No quotas yet."
5. Choose **Advanced**. Expect **When full** and **Warn at percent**. Choose **Simple** to hide them. The choice is stored as `ar-settings-mode`.
6. Save an each-person token quota with limit `0`. Expect "Quota saved." and a full bar.
7. Open the account menu and choose **Profile**. Expect **My usage** with this month's quantity and the quotas that apply.
8. Open **Chat** and send a message. Expect an alert that starts with "Quota reached" and names the token quota. The optimistic bubbles are removed.
9. Return to **Quotas** and remove the limit-0 quota. Expect "Quota removed." Chat works again. Leave the 100,000 token quota in place.
10. Narrow to 375px and switch to dark. Usage, quotas, profile and the blocked chat stay on the same tokens. Loading uses skeletons.

## Deferred

SaaS invoicing is out of scope. Currency is not converted (OQ-04). Counters stay in the process until Valkey is bound (OQ-43). The usage-rollup schedule is not registered on the worker; reports rebuild daily totals when they are read.
