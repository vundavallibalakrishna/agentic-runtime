# Microsoft 365 Calendar

List events, find free time and create an event on Microsoft 365.

**Implementation:** Built
**Category:** Calendar
**Auth:** oauth_authorization_code, bearer
**Verification:** Not live-tested
**Note:** Implemented from Microsoft Graph calendar docs. No mailbox was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade

## Setup

1. Open the same Entra app page as Teams: https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade.
2. Add delegated Microsoft Graph permissions Calendars.ReadWrite and offline_access. Admin consent if required.
3. Create a client secret. The authorize URL is https://login.microsoftonline.com/common/oauth2/v2.0/authorize.
4. The token URL is https://login.microsoftonline.com/common/oauth2/v2.0/token.
5. Creating an event asks for approval. Times are sent in UTC.

## Scopes

- `Calendars.ReadWrite`
- `offline_access`

## Settings

- None.

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `m365cal_list_events` | List events | R0 | List events on the signed-in calendar. |
| `m365cal_find_free` | Find free time | R0 | Find free time for one or more schedules. |
| `m365cal_create_event` | Create an event | W2 | Create an event on the signed-in calendar. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
