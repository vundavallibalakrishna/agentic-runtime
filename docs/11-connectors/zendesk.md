# Zendesk

Search tickets, read a ticket, create a ticket and add a comment.

**Implementation:** Built
**Category:** Work
**Auth:** basic, bearer
**Verification:** Not live-tested
**Note:** Not live-tested. Tools match Zendesk Support API examples. No subdomain was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://support.zendesk.com/hc/en-us/articles/4408889192858

## Setup

1. Open Admin Center, Apps and integrations, APIs, Zendesk API. Enable token access and add a token. The guide is the provider page.
2. Username is the agent email plus /token, for example you@company.com/token. The secret is the API token.
3. Set the site URL to https://your-subdomain.zendesk.com.
4. OAuth scopes, if you use a bearer token from your own Zendesk OAuth client, are tickets:read and tickets:write. Skip tickets:write when comments and new tickets stay off.
5. Creating a ticket or adding a comment asks for approval.

## Scopes

- `tickets:read`
- `tickets:write`

## Settings

- Site URL (`baseUrl`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `zendesk_search_tickets` | Search tickets | R0 | Search tickets. |
| `zendesk_read_ticket` | Read a ticket | R0 | Read one ticket. |
| `zendesk_create_ticket` | Create a ticket | W2 | Create a ticket. |
| `zendesk_add_comment` | Add a comment | W2 | Add a public comment to a ticket. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
