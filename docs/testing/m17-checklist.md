# M17 visual checklist

Sign in as the dev admin. The GRC pack is installed for the dev tenant. A seeded AWS Config collection has already failed, so Tests shows `aws-config` and Findings shows an open item. Evidence is captured and not yet linked, so the Evidence page still says nothing is linked until you link it yourself.

Seed data is the dev tenant. The admin is `admin@dev.local`. The starter catalogues from M16 are loaded. `fake-llm` answers chat. No model API key.

## Start

```bash
make bootstrap
make migrate
uv run alembic -c packs/grc/alembic.ini upgrade head
make seed
make dev
```

Web: http://localhost:3000. API: http://localhost:8000. Dev login: **Sign in as admin@dev.local** on `/login`.

Host ports come from `.env`. `make ports-check` names a busy port. `make dev AUTO_PORTS=1` moves it.

`make migrate` stays the core history. The pack command creates schema `grc`. HTTP rows for tests and findings stay on the process store (OQ-49, OQ-50).

Earlier screens stay on Chat, Agents, Tools, Knowledge, Memory, Skills, Routines, Channels, Approvals, Runs, Models, Computers, Users, Usage, Quotas, Evaluations, Platform health, Assurance, and the M16 GRC catalogue.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading and a **GRC** item in the sidebar.
2. Open **GRC**. Expect NIST CSF 2.0. Open **Tests**. Expect `aws-config` with **Fail**.
3. Expect the procedure “Fail when an AWS Config rule is not compliant.” Choose **Run test**. Expect “The test failed. A finding is open.”
4. Open **Findings**. Expect `aws-config failed`, severity high, status Open.
5. Leave evidence on “Choose evidence” and choose **Close finding**. Expect “Closure needs a verified evidence item.”
6. Choose the `grc_aws` evidence item and close again. Expect “Finding closed.” and status Closed.
7. Open **Connectors**. Expect AWS, Azure, Google Cloud, Okta, Entra ID, Google Workspace, GitHub, GitLab, Jira and ServiceNow. Cloud and identity cards say Read only. Jira and ServiceNow say writes wait for approval. AWS shows a captured count.
8. Open **Evidence**. With no link yet, expect “No evidence is linked to a control yet.” The captured AWS item can be linked from the form.
9. Narrow to 375px and switch to dark. Tests, findings and connectors stay on the same tokens.

## Deferred

P2 collectors (endpoint, vulnerability, HR and SIEM) are not installed. Entitlement rows stay evidence until M19-T02. Questionnaires, vendors, policies, risk and the auditor portal remain later pack tasks. The CCM activity writes the finding for a scripted failure; an agent call to `grc.findings.create` still waits for approval (OQ-50).
