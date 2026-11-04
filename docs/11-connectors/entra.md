# Microsoft Entra ID

List and read users and groups, and read app registrations and sign-in logs.

**Category:** Identity
**Auth:** oauth_client_credentials, oauth_authorization_code
**Verification:** Not live-tested
**Note:** Not live-tested. Tools match Microsoft Graph examples. No directory was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app

## Setup

1. Open Entra app registrations and choose New registration. The guide is the provider page. Accounts in this organizational directory only.
2. Certificates and secrets, New client secret. Client id is the application id. The secret is the client secret value.
3. API permissions, Microsoft Graph, application permissions: User.Read.All, Group.Read.All, Application.Read.All and AuditLog.Read.All. Grant admin consent.
4. The token request uses scope https://graph.microsoft.com/.default. Set Tenant id to the directory id.
5. A delegated sign-in can use the same permissions as delegated scopes plus offline_access. These tools are reads.
6. Sign-in logs need a licence that includes them, and AuditLog.Read.All. The connector does not write directory objects.

## Scopes

- `https://graph.microsoft.com/.default`

## Settings

- Tenant id (`tenantId`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `entra_list_users` | List users | R0 | List users. |
| `entra_read_user` | Read a user | R0 | Read one user. |
| `entra_list_groups` | List groups | R0 | List groups. |
| `entra_read_group` | Read a group | R0 | Read one group. |
| `entra_list_apps` | List app registrations | R0 | List application registrations. |
| `entra_list_signins` | List sign-in logs | R0 | List directory sign-in logs. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
