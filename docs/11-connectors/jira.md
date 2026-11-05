# Jira

Search issues, create and update an issue, and add a comment.

**Implementation:** Built
**Category:** Work
**Auth:** basic, oauth_authorization_code
**Verification:** Not live-tested
**Note:** Implemented from the Jira Cloud REST v3 examples. No site was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://developer.atlassian.com/console/myapps/

## Setup

1. For an API token, open https://id.atlassian.com/manage-profile/security/api-tokens and create a token.
2. Basic auth uses the Atlassian account email as the username and the token as the secret.
3. Set the site URL, for example https://your-site.atlassian.net.
4. For OAuth, create an app at https://developer.atlassian.com/console/myapps/ with Jira scopes read:jira-work and write:jira-work.
5. Authorize URL https://auth.atlassian.com/authorize. Token URL https://auth.atlassian.com/oauth/token.
6. Creating, updating and commenting ask for approval.

## Scopes

- `read:jira-work`
- `write:jira-work`

## Settings

- Site URL (`baseUrl`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `jira_search` | Search issues | R0 | Search issues with JQL. |
| `jira_create_issue` | Create an issue | W2 | Create an issue in a project. |
| `jira_update_issue` | Update an issue | W2 | Update an issue's summary or description. |
| `jira_add_comment` | Add a comment | W2 | Add a comment to an issue. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
