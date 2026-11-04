# M26 checklist

Proof date: 2026-11-04. Chat model: Qwen/Qwen3-32B through DeepInfra (`https://api.deepinfra.com/v1/openai`). The provider key was read from `AR_CERT_LLM_API_KEY` and is not in this file. The API for the model run listened on `18127` with `AR_DURABLE_STATE=memory`. Postgres on 5432 and the apps on 8000, 8001 and 8013 were not used.

## Per connector

Exactly one label. A stand-in in a unit test is not a live call.

| Connector | Label | What was actually called |
|---|---|---|
| Email | (a) live, local service | SMTP send to Mailpit on `127.0.0.1:11025`. The mailbox API then listed subject `M26 proof` from `ada@example.com`. Mailpit is a local test server, not a customer provider. |
| Slack | (c) not live-tested | Recorded Slack Web API examples in unit tests. No workspace was connected. |
| Microsoft Teams | (c) not live-tested | Recorded Microsoft Graph examples in unit tests. No tenant was connected. |
| Google Calendar | (c) not live-tested | Recorded Calendar API examples in unit tests. No Google account was connected. |
| Microsoft 365 Calendar | (c) not live-tested | Recorded Graph calendar examples in unit tests. No mailbox was connected. |
| Google Drive | (c) not live-tested | Recorded Drive API examples in unit tests. No Drive was connected. |
| SharePoint and OneDrive | (c) not live-tested | Recorded Graph drive examples in unit tests. No drive was connected. |
| S3-compatible storage | (b) provider API via a reference server | Put and get of `proof.txt` (`m26 proof object`) against SeaweedFS on `127.0.0.1:18333`. The MinIO image could not be pulled. Not AWS. |
| Jira | (c) not live-tested | Recorded Jira Cloud REST examples in unit tests. No site was connected. |
| GitHub | (a) live | `GET https://api.github.com/repos/octocat/Hello-World` returned 200, `full_name` `octocat/Hello-World`, `private` false. The connector tool `github_read_file` returned `{"path":"README","text":"Hello World!\n"}`. `github_create_issue` created `https://api.github.com/repos/vundavallibalakrishna/agentic-runtime/issues/35`. The token was a GitHub token available to this run, not a customer account. |
| Confluence | (c) not live-tested | Recorded Confluence Cloud REST examples in unit tests. No site was connected. |
| Notion | (c) not live-tested | Recorded Notion API examples in unit tests. No workspace was connected. |

## Real model

The agent was told to call `github_read_file` for `octocat/Hello-World` `README`. The run completed. The summary was: The first heading from the README file is: "Hello World!".

Writes (`email_send`, `s3_put`, `github_create_issue`) are W2. The tool test and a chat turn stopped at `awaiting_approval` before the provider was called. The same-user decision is blocked by segregation of duties (`sod_violation`). The side effects above were made by the connector runtime against the live services, which is the code the approval resumes.

## Durability

- [x] `libs/ar_domain/tests/integration/test_m26_durable.py` passed. A GitHub install, a named secret `vendor`, an OAuth state and a credential grant were still present after `bind_store` on a new process. The ciphertext columns do not hold the plaintext verifier or tokens.

## Screens

Playwright captures the catalog and the Notion page in light and dark at desktop and mobile widths. Walkthrough: `docs/testing/m26/walkthrough.webm`.
