# M14 visual checklist

Sign in as the dev admin and use Assurance for evidence, holds, retention, the AI register, guests and binders. Export your own data from the same page. Open the guest portal without a workspace session.

Seed data is the dev tenant. The admin is `admin@dev.local`. A sealed desk note is already in Evidence. A compliance officer is available as the second person on a hold. `fake-llm` answers chat. No model API key.

## Start

```bash
make bootstrap
make dev
make seed
```

Web: http://localhost:3000. API: http://localhost:8000. Dev login: **Sign in as admin@dev.local** on `/login`.

Host ports come from `.env`. `make ports-check` names a busy port. `make dev AUTO_PORTS=1` moves it.

Earlier screens stay on Chat, Agents, Tools, Knowledge, Memory, Skills, Routines, Channels, Approvals, Runs, Models, Computers, Users, Usage, Quotas, Evaluations and Platform health.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading.
2. Open **Assurance**. Expect the Evidence tab. An empty vault says "No evidence yet." A durable database does not invent a row until you seal one.
3. Type a note and choose **Seal evidence**. Expect "Evidence sealed."
4. Open **Holds**. Expect the two-person note. Creating a hold with yourself as approver is refused.
5. Open **Retention**. Expect `evidence_item` at 2555 days. A schedule under 180 days is refused by the API.
6. Open **Guests**. Invite an email. Expect "Invitation recorded." An empty list says "No guests."
7. Choose **Export my data**. Expect "Your export is ready."
8. Open `/guest` signed out or in a private window. Expect **Guest access**, the email form, and the note that chat and tools stay closed. A failed sign-in shows the error and does not reveal whether the email exists.
9. Narrow to 375px and switch to dark. Assurance and the guest portal stay on the same tokens.

## Deferred

Record rows are created in revision `0023` together so Alembic keeps one head (OQ-47). HTTP assurance state stays on the process store. A full OWASP ZAP container scan stays on the nightly workflow. The 150-case red-team corpus is still the smaller seeded set from M13.
