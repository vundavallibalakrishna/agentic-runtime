# Microsoft Teams

List channels in a team and post a message.

**Category:** Communication
**Auth:** oauth_authorization_code, bearer
**Verification:** Not live-tested
**Note:** Implemented from Microsoft Graph docs. No tenant was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade

## Setup

1. Open Entra app registrations: https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade.
2. New registration. Platform is Web. Redirect URI is this platform's service-connection callback.
3. API permissions, Microsoft Graph, delegated: Channel.ReadBasic.All, ChannelMessage.Send and offline_access.
4. Grant admin consent when the tenant requires it.
5. Certificates & secrets, New client secret. Put the application id in Client id and the secret in the connection.
6. A channel post asks for approval. The team id is the id in the Teams link.

## Scopes

- `Channel.ReadBasic.All`
- `ChannelMessage.Send`
- `offline_access`

## Settings

- None.

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `teams_list_channels` | List channels | R0 | List channels in a team. |
| `teams_post_message` | Post a message | W2 | Post a message to a channel. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
