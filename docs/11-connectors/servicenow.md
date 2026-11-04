# ServiceNow

Read, create and update incidents and changes, and query a table.

**Category:** Work
**Auth:** basic, oauth_authorization_code
**Verification:** Not live-tested
**Note:** Not live-tested. Tools match ServiceNow Table API examples. No instance was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://www.servicenow.com/docs/bundle/yokohama-platform-security/page/administer/security/concept/c_OAuthAuthorizationCodeAPI.html

## Setup

1. This connector uses your ServiceNow instance. The platform does not hold a ServiceNow account.
2. Basic auth: the username is the instance user and the secret is the password. The user needs the itil role, or sn_incident_read plus sn_change_read when writes stay off.
3. Set the site URL to https://your-instance.service-now.com.
4. OAuth: in the instance open System OAuth, Application Registry, Create an OAuth API endpoint for external clients. The docs are at the provider page.
5. Redirect URL is this platform's service-connection callback. The scope useraccount identifies the user.
6. Creating or updating an incident or a change asks for approval. Skip those tools, and the itil write role, when you only want reads.

## Scopes

- `useraccount`

## Settings

- Instance URL (`baseUrl`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `servicenow_get_incident` | Read an incident | R0 | Read one incident by sys_id. |
| `servicenow_create_incident` | Create an incident | W2 | Create an incident. |
| `servicenow_update_incident` | Update an incident | W2 | Update an incident. |
| `servicenow_get_change` | Read a change | R0 | Read one change request by sys_id. |
| `servicenow_create_change` | Create a change | W2 | Create a change request. |
| `servicenow_update_change` | Update a change | W2 | Update a change request. |
| `servicenow_query_table` | Query a table | R0 | Query a table with an encoded query. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
