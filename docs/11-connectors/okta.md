# Okta

List and read users and groups, list app assignments, and deactivate a user.

**Implementation:** Built
**Category:** Identity
**Auth:** bearer, oauth_authorization_code
**Verification:** Not live-tested
**Note:** Not live-tested. Tools match Okta Users, Groups and Apps API examples. No org was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://developer.okta.com/docs/guides/create-an-api-token/main/

## Setup

1. In the Okta admin console open Security, API, Tokens, Create token. The guide is the provider page. The token is shown once.
2. Paste the token as a bearer secret. The connector sends it as Authorization: SSWS. Do not type the SSWS prefix yourself.
3. Set the site URL to your org, for example https://dev-123456.okta.com.
4. The token's admin role needs users and groups read. App assignment reads need an apps read role. Deactivate needs a user-management role. Leave that tool off when you only want reads.
5. OAuth service-app scopes are okta.users.read, okta.groups.read, okta.apps.read and okta.users.manage. Authorize and token URLs are on your org under /oauth2/v1/.
6. Deactivating a user asks for approval.

## Scopes

- `okta.users.read`
- `okta.users.manage`
- `okta.groups.read`
- `okta.apps.read`

## Settings

- Org URL (`baseUrl`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `okta_list_users` | List users | R0 | List users. |
| `okta_read_user` | Read a user | R0 | Read one user. |
| `okta_list_groups` | List groups | R0 | List groups. |
| `okta_read_group` | Read a group | R0 | Read one group. |
| `okta_list_app_users` | List app assignments | R0 | List users assigned to an app. |
| `okta_deactivate_user` | Deactivate a user | W2 | Deactivate a user. This asks for approval. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
