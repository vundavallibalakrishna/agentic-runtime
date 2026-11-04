# Notion

Search, read a page or database, and create a page.

**Category:** Work
**Auth:** bearer, oauth_authorization_code
**Verification:** Not live-tested
**Note:** Implemented from the Notion API 2022-06-28 examples. No workspace was connected.
**Local rate limit:** 20 calls a minute.
**Provider page:** https://www.notion.so/my-integrations

## Setup

1. Open https://www.notion.so/my-integrations and choose New integration. Type Internal.
2. Capabilities: Read content for search and read. Insert content to create a page. Update content only if you will edit.
3. Copy the internal integration secret and store it as a bearer token.
4. In Notion, open the page or database, then Connections, and add the integration. Unshared pages stay invisible.
5. A public OAuth integration uses https://api.notion.com/v1/oauth/authorize and https://api.notion.com/v1/oauth/token.
6. The connector sends Notion-Version 2022-06-28. Creating a page asks for approval.

## Scopes

- `Read content`
- `Update content`
- `Insert content`

## Settings

- None.

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `notion_search` | Search | R0 | Search pages and databases shared with the integration. |
| `notion_read_page` | Read a page | R0 | Read a page. |
| `notion_read_database` | Read a database | R0 | Read a database. |
| `notion_create_page` | Create a page | W2 | Create a page under a parent page. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
