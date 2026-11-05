# Google Calendar

List events, find free time and create an event.

**Implementation:** Built
**Category:** Calendar
**Auth:** oauth_authorization_code, bearer
**Verification:** Not live-tested
**Note:** Implemented from the Calendar API docs. No Google account was connected.
**Local rate limit:** 40 calls a minute.
**Provider page:** https://console.cloud.google.com/apis/credentials

## Setup

1. Open https://console.cloud.google.com/apis/library/calendar-json.googleapis.com and enable the Google Calendar API.
2. Configure the OAuth consent screen, then open https://console.cloud.google.com/apis/credentials.
3. Create an OAuth client ID of type Web application. Add this platform's callback as an authorized redirect URI.
4. Scopes: https://www.googleapis.com/auth/calendar.events and https://www.googleapis.com/auth/calendar.freebusy.
5. Put the client id and client secret on the connection. Creating an event asks for approval.
6. A bearer token you already hold can be pasted instead of completing OAuth. It is not shown again.
7. Calendar id defaults to primary, which is the signed-in calendar.

## Scopes

- `https://www.googleapis.com/auth/calendar.events`
- `https://www.googleapis.com/auth/calendar.freebusy`

## Settings

- None.

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `gcal_list_events` | List events | R0 | List events on a calendar. |
| `gcal_find_free` | Find free time | R0 | Find when a calendar is free. |
| `gcal_create_event` | Create an event | W2 | Create an event on a calendar. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
