# Confluence

Search, read a page, and create or update a page.

**Category:** Work
**Auth:** basic, oauth_authorization_code
**Verification:** Not live-tested
**Note:** Implemented from the Confluence Cloud REST examples. No site was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://developer.atlassian.com/console/myapps/

## Setup

1. API token: https://id.atlassian.com/manage-profile/security/api-tokens. Username is the account email.
2. Set the site URL, for example https://your-site.atlassian.net. Cloud paths start with /wiki.
3. OAuth app: https://developer.atlassian.com/console/myapps/ with Confluence scopes read:confluence-content.all and write:confluence-content.
4. Writing a page asks for approval. The body is storage format.

## Scopes

- `read:confluence-content.all`
- `write:confluence-content`

## Settings

- Site URL (`baseUrl`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `confluence_search` | Search pages | R0 | Search pages with CQL. |
| `confluence_read_page` | Read a page | R0 | Read a page, including its storage body. |
| `confluence_write_page` | Create or update a page | W2 | Create a page, or update one when page_id is set. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
