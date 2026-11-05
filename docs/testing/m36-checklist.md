# M36 checklist — connector live pack

Every catalogue connector is **built**. Verification is separate: live-tested, tested on a reference API, or not live-tested. This harness does not invent OAuth apps and does not store tokens. CI runs the dry path.

GitHub stays the reference live connector. Its canary reads `octocat/Hello-World` `README`, the same public file the M31 proof read. That read does not demote the live label.

## Dry run

No provider is called. A token sitting in the environment is ignored until `AR_M36_LIVE=1`.

```bash
uv run pytest libs/ar_domain/tests/unit/test_m36_live_pack.py -q
make live-pack
```

`make live-pack` prints one skipped row per connector. The catalog label stays as it was. `docs/testing/m36/ledger.json` stays empty unless you pass `--record` after a live success.

## Live run

Set the flag and only the env for the connectors you can call. Values are read from the environment. They are not printed and not written into the ledger.

```bash
AR_M36_LIVE=1 AR_M36_ONLY=github uv run python -m ar_domain.connectors.live_pack
```

`AR_M36_ONLY` is a comma-separated slug list. Omit it to consider every connector. A connector whose env is missing is `missing_env` and is not called. The missing list is the variable names.

A successful read sets that row's verification to `live` in the report. The catalog source stays `not_live` until you record the ledger and the process reads it.

```bash
AR_M36_LIVE=1 AR_M36_ONLY=slack AR_M36_SLACK_TOKEN=... \
  uv run python -m ar_domain.connectors.live_pack --record
```

`--record` updates `docs/testing/m36/ledger.json`, or `AR_M36_LEDGER` when that path is set. A row is stored only when the read succeeded. The excerpt keeps ids and names and drops message text. A value that still contains a token prefix is refused and not stored. Review the diff before committing it. The API shows `live` for a `not_live` connector when that ledger row is present. GitHub and S3 are not demoted by an empty or failed row.

## Writes

Writes stay off unless both flags are set. Without them the report says `held` or `awaiting_approval` and the provider is not called.

```bash
AR_M36_LIVE=1 AR_M36_WRITE=1 AR_M36_WRITE_APPROVED=1 AR_M36_ONLY=github \
  AR_M36_GITHUB_TOKEN=... AR_M36_GITHUB_OWNER=... AR_M36_GITHUB_REPO=... \
  uv run python -m ar_domain.connectors.live_pack
```

`AR_M36_WRITE=1` without `AR_M36_WRITE_APPROVED=1` records `awaiting_approval`. Okta's write deactivates the user in `AR_M36_OKTA_USER_ID`. Leave that variable unset unless you mean it.

## Environment

These names are harness inputs. They are not service settings and they are not in `.env.example`.

| Connector | Read | Required env | Write env, in addition to the two flags |
|---|---|---|---|
| Email | `email_list` | `AR_M36_EMAIL_USERNAME`, `AR_M36_EMAIL_PASSWORD`, `AR_M36_EMAIL_SMTP_HOST`, `AR_M36_EMAIL_IMAP_HOST` | `AR_M36_EMAIL_TO` |
| Slack | `slack_list_channels` | `AR_M36_SLACK_TOKEN` | `AR_M36_SLACK_CHANNEL` |
| Teams | `teams_list_channels` | `AR_M36_TEAMS_TOKEN`, `AR_M36_TEAMS_TEAM` | `AR_M36_TEAMS_CHANNEL` |
| Google Calendar | `gcal_list_events` | `AR_M36_GCAL_TOKEN` | none |
| Microsoft 365 Calendar | `m365cal_list_events` | `AR_M36_M365_CALENDAR_TOKEN` | none |
| Google Drive | `gdrive_list` | `AR_M36_GDRIVE_TOKEN` | none |
| SharePoint and OneDrive | `sharepoint_list` | `AR_M36_SHAREPOINT_TOKEN` | none |
| S3-compatible storage | `s3_list` | `AR_M36_S3_ACCESS_KEY`, `AR_M36_S3_SECRET_KEY`, `AR_M36_S3_ENDPOINT`, `AR_M36_S3_BUCKET` | none |
| Jira | `jira_search` | `AR_M36_JIRA_EMAIL`, `AR_M36_JIRA_TOKEN`, `AR_M36_JIRA_BASE_URL` | `AR_M36_JIRA_PROJECT` |
| GitHub | `github_read_file` | none for the public README | `AR_M36_GITHUB_TOKEN`, `AR_M36_GITHUB_OWNER`, `AR_M36_GITHUB_REPO` |
| Confluence | `confluence_search` | `AR_M36_CONFLUENCE_EMAIL`, `AR_M36_CONFLUENCE_TOKEN`, `AR_M36_CONFLUENCE_BASE_URL` | `AR_M36_CONFLUENCE_SPACE` |
| Notion | `notion_search` | `AR_M36_NOTION_TOKEN` | `AR_M36_NOTION_PARENT` |
| ServiceNow | `servicenow_query_table` | `AR_M36_SERVICENOW_USERNAME`, `AR_M36_SERVICENOW_PASSWORD`, `AR_M36_SERVICENOW_BASE_URL` | none |
| Salesforce | `salesforce_query` | `AR_M36_SALESFORCE_TOKEN`, `AR_M36_SALESFORCE_BASE_URL` | `AR_M36_SALESFORCE_OBJECT`, `AR_M36_SALESFORCE_FIELDS` |
| Zendesk | `zendesk_search_tickets` | `AR_M36_ZENDESK_EMAIL` (`you@company.com/token`), `AR_M36_ZENDESK_TOKEN`, `AR_M36_ZENDESK_BASE_URL` | none |
| HubSpot | `hubspot_list_deals` | `AR_M36_HUBSPOT_TOKEN` | `AR_M36_HUBSPOT_EMAIL` |
| Okta | `okta_list_users` | `AR_M36_OKTA_TOKEN`, `AR_M36_OKTA_BASE_URL` | `AR_M36_OKTA_USER_ID` (deactivates that user) |
| Entra ID | `entra_list_users` | `AR_M36_ENTRA_TENANT`, `AR_M36_ENTRA_CLIENT_ID`, `AR_M36_ENTRA_CLIENT_SECRET` | none |
| AWS | `aws_list_buckets` | `AR_M36_AWS_ACCESS_KEY`, `AR_M36_AWS_SECRET_KEY` | none |
| Azure | `azure_list_resource_groups` | `AR_M36_AZURE_TENANT`, `AR_M36_AZURE_CLIENT_ID`, `AR_M36_AZURE_CLIENT_SECRET`, `AR_M36_AZURE_SUBSCRIPTION` | none |
| Google Cloud | `gcp_list_projects` | `AR_M36_GCP_SERVICE_ACCOUNT_JSON` | none |

Optional settings: `AR_M36_EMAIL_FROM`, `AR_M36_S3_REGION`, `AR_M36_AWS_REGION`, `AR_M36_AWS_ROLE_ARN`, `AR_M36_AWS_ENDPOINT`, `AR_M36_GCP_PROJECT`, `AR_M36_GCP_ZONE`.

Google Calendar and Google Drive take a pasted bearer. Teams lists channels and does not read message text. SharePoint calls the signed-in OneDrive and does not take a site id.

## Labels on this commit

| Connector | Built | Verification |
|---|---|---|
| Email | Built | Live-tested, local SMTP |
| Slack | Built | Not live-tested |
| Teams | Built | Not live-tested |
| Google Calendar | Built | Not live-tested |
| Microsoft 365 Calendar | Built | Not live-tested |
| Google Drive | Built | Not live-tested |
| SharePoint and OneDrive | Built | Not live-tested |
| S3-compatible storage | Built | Reference API |
| Jira | Built | Not live-tested |
| GitHub | Built | Live-tested |
| Confluence | Built | Not live-tested |
| Notion | Built | Not live-tested |
| ServiceNow | Built | Not live-tested |
| Salesforce | Built | Not live-tested |
| Zendesk | Built | Not live-tested |
| HubSpot | Built | Not live-tested |
| Okta | Built | Not live-tested |
| Entra ID | Built | Not live-tested |
| AWS | Built | Not live-tested |
| Azure | Built | Not live-tested |
| Google Cloud | Built | Not live-tested |

## Out of scope

GRC collectors stay removed. Analytics, Temporal durability and the browser track are other milestones. This harness does not call them.
