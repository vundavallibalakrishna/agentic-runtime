# Connector proof plan

Written 24 November 2026. It answers one question: how do the 25 connectors move from "built" to "run against the real service", and what does the owner need to supply for each.

## Where it stands

- 25 connectors, 100 tools ([catalogue](../../libs/ar_domain/src/ar_domain/connectors/catalog.py)). Each tool is a real HTTP call through `connectors/dispatch.py`; OAuth, token refresh and sealed token storage are real code.
- One connector, GitHub, has been called against the real service. S3 has been called against a reference server. The rest have been tested against recorded or mocked answers only.
- The live certification has a sign-in probe for some connectors ([live_certification_run.py](../../scripts/live_certification_run.py), `_stage11`). Every one has been skipped in every run, because no token was supplied. A probe is a "who am I" call, not a tool call.
- The tool certification leaves `connectors.*` out of its coverage rule, so a connector tool with no case does not fail a run.

So the claim that can be made today is "built", and for GitHub "live-tested". Nothing else.

## What counts as proof

A connector is proven when, on a fresh install from the certification job, with an account the owner supplied:

1. the connector is installed and a connection is made with the supplied credential, through the product's own API;
2. every read tool returns a real object from that account;
3. one write tool makes a change the run then removes, after the approval the tool's risk class requires;
4. a wrong credential is refused in words, and nothing is logged that holds the credential.

No model is needed for any of this. The calls are console tool tests, as in the tool certification, so a connector run costs nothing on the model provider's account.

## How it is built

One change, in the certification and not in the product:

- A `connectors` part for `scripts/certify_stack.sh`, beside `live`, `tools` and `agents`. It needs no model key.
- Cases in `scripts/tool_certification.py` for each connector, in the form the built-in tools already use. A connector with no credential in the environment is `blocked`, with the name of what to supply. A connector with one is tested, and a failure fails the run.
- The coverage rule then includes `connectors.*`, and `scripts/check_certification_cases.py` checks it, so a new connector tool cannot be added without a case.
- Credentials are repository secrets, one per connector, named `AR_CERT_<CONNECTOR>_...`. The repository is public: the job masks them, and the evidence holds counts and error codes, not content.

Each connector's guide in this folder gets its verification line from the run that proved it, with the run's number and date.

## Order, and what each needs

The order is by how little it asks of the owner, not by importance. The account notes are what each provider offered when this was written; confirm them when signing up.

| Step | Connectors | What the owner supplies | Tools |
|---|---|---|---|
| 1 | GitHub, REST, Email, S3 | A GitHub token for a scratch repository. Nothing for the others: REST calls a public address, email uses the mail server the job already starts, S3 uses the install's own object store | 14 |
| 2 | Slack, Notion, Jira, Confluence | A free Slack workspace with a bot token; a free Notion workspace with an integration token; a free Atlassian cloud site with an API token (one site covers Jira and Confluence) | 15 |
| 3 | Gmail, Google Calendar, Google Drive | One Google account and an OAuth client in test mode, with a refresh token | 10 |
| 4 | Outlook, Microsoft 365 Calendar, SharePoint and OneDrive, Teams, Entra ID | A Microsoft 365 tenant with one licensed user, and an app registration. This is the hardest to get free | 18 |
| 5 | HubSpot, Salesforce, ServiceNow, Zendesk | A HubSpot developer account; a Salesforce Developer Edition org; a ServiceNow developer instance; a Zendesk trial, which expires | 23 |
| 6 | Okta, AWS, Azure, GCP | An Okta developer org; a read-only key in a scratch account of each cloud | 20 |

Steps 1 and 2 are about a day of the owner's time to create accounts, and prove 29 of the 100 tools. They are also the ones most customers ask about first.

## What this plan does not cover

- Systems with no connector: GitLab, Bitbucket, SAP, Workday, Box, Dropbox, Zoom, Asana, Linear, Snowflake, BigQuery, Databricks. A customer reaches them today through a remote MCP server, an imported OpenAPI document or the REST connector. Those three paths are themselves unit-tested only and need the same kind of proof; that is a separate piece of work.
- Depth. Most connectors have 3 to 7 tools. Proof says the tools that exist work, not that they are enough.
- Slack and Teams as places to talk to an agent. Replies are not sent (OQ-161, OQ-194).
