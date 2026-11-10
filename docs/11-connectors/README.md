# Connectors

A connector is a ready-made set of tools. The customer connects their own account. The platform does not hold a provider account for them.

Every row below is **built**: the tools, setup steps and error messages ship in the product. Verification is separate:

- **Live-tested.** A real call was made. The checklist says what was called.
- **Tested on the provider API.** A public endpoint or a reference server such as MinIO answered.
- **Not live-tested.** The tools match recorded provider examples. No customer account was used. The [M36 harness](../testing/m36-checklist.md) promotes this to live-tested when a canary records a read. CI skips that call when the token is absent.

| Connector | Built | Verification | Guide |
|---|---|---|---|
| [Email](email.md) | Built | Live-tested | `docs/11-connectors/email.md` |
| [Slack](slack.md) | Built | Not live-tested | `docs/11-connectors/slack.md` |
| [Microsoft Teams](teams.md) | Built | Not live-tested | `docs/11-connectors/teams.md` |
| [Google Calendar](gcal.md) | Built | Not live-tested | `docs/11-connectors/gcal.md` |
| [Microsoft 365 Calendar](m365-calendar.md) | Built | Not live-tested | `docs/11-connectors/m365-calendar.md` |
| [Google Drive](gdrive.md) | Built | Not live-tested | `docs/11-connectors/gdrive.md` |
| [SharePoint and OneDrive](sharepoint.md) | Built | Not live-tested | `docs/11-connectors/sharepoint.md` |
| [S3-compatible storage](s3.md) | Built | Tested on the provider API | `docs/11-connectors/s3.md` |
| [Jira](jira.md) | Built | Not live-tested | `docs/11-connectors/jira.md` |
| [GitHub](github.md) | Built | Live-tested | `docs/11-connectors/github.md` |
| [Confluence](confluence.md) | Built | Not live-tested | `docs/11-connectors/confluence.md` |
| [Notion](notion.md) | Built | Not live-tested | `docs/11-connectors/notion.md` |
| [ServiceNow](servicenow.md) | Built | Not live-tested | `docs/11-connectors/servicenow.md` |
| [Salesforce](salesforce.md) | Built | Not live-tested | `docs/11-connectors/salesforce.md` |
| [Zendesk](zendesk.md) | Built | Not live-tested | `docs/11-connectors/zendesk.md` |
| [HubSpot](hubspot.md) | Built | Not live-tested | `docs/11-connectors/hubspot.md` |
| [Okta](okta.md) | Built | Not live-tested | `docs/11-connectors/okta.md` |
| [Microsoft Entra ID](entra.md) | Built | Not live-tested | `docs/11-connectors/entra.md` |
| [AWS](aws.md) | Built | Not live-tested | `docs/11-connectors/aws.md` |
| [Azure](azure.md) | Built | Not live-tested | `docs/11-connectors/azure.md` |
| [Google Cloud](gcp.md) | Built | Not live-tested | `docs/11-connectors/gcp.md` |
| [Gmail](gmail.md) | Built | Not live-tested | `docs/11-connectors/gmail.md` |
| [Outlook](outlook.md) | Built | Not live-tested | `docs/11-connectors/outlook.md` |
| [REST API](rest.md) | Built | Not live-tested | `docs/11-connectors/rest.md` |

