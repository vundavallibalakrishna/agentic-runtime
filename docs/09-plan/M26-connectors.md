# M26 — Connector catalog

Depends on M25. A customer installs a ready-made connector, follows the provider's own app-registration steps, connects an account, tests it, and attaches its tools to an agent.


## M26-T01 Durable credentials

**Spec:** [m26-connectors](../06-security/m26-connectors.md), [OQ-59](../open-questions.md).

**Do:**

- Store connector installs, OAuth state, OAuth grants and named secrets in Postgres (revision 0028).
- Encrypt tokens, verifiers and named secrets. API responses do not return them.
- A new process can load the same rows after a restart.

**Done when:** an install, an OAuth state, a grant and a named secret are still present after the API process is replaced.

**Tests:** `libs/ar_domain/tests/unit/test_m26_connectors.py`, `libs/ar_domain/tests/integration/test_m26_durable.py`.

## M26-T02 Connector runtime

**Spec:** [11-connectors](../11-connectors/README.md).

**Do:**

- One shared HTTP runtime: auth from a service connection, pagination, local rate limits, and 401, 403, 404 and 429 messages.
- Thin definitions for email, Slack, Teams, Google Calendar, Microsoft 365 Calendar, Google Drive, SharePoint/OneDrive, S3, Jira, GitHub, Confluence and Notion.
- Reads are R0. Writes are W2 and wait for approval.
- Each tool can be turned off on the install.

**Done when:** a mocked provider call returns the documented shape, and a disabled write does not run.

**Tests:** `test_m26_connectors.py`.

## M26-T03 Catalog screen

**Spec:** [ux-quality](../08-quality/ux-quality.md).

**Do:**

- A catalog with categories, search, status badges and a link to each connector.
- An install flow that shows the setup steps, the scopes and the provider's app page.
- The agent editor can attach individual connector tools.

**Done when:** Playwright captures the catalog and a connector page in light and dark at desktop and mobile widths.

**Tests:** `apps/web/e2e/m26-connectors.spec.ts`, `apps/web/src/components/connectors/connectors-screen.test.tsx`.

## M26-T04 Proof

**Spec:** [m26-checklist](../testing/m26-checklist.md).

**Do:**

- Record, for each connector, exactly one of live, public provider API, or not live-tested.
- Prove a public GitHub read, an S3 read and write against MinIO, and an email send through a local SMTP stand-in.
- Where those services can be called from chat, use Qwen/Qwen3-32B.

**Done when:** the checklist table matches the badges in the catalog.

## Out of scope

Further connector products, orchestration and exposing agents.

