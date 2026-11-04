# GitHub

List repositories, issues and pull requests, read a file, open an issue and comment.

**Category:** Work
**Auth:** bearer, oauth_authorization_code
**Verification:** Live-tested
**Note:** A public read of octocat/Hello-World returned the README heading. An issue was created on a repository the proof token could write. That token is not a customer account.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://github.com/settings/tokens/new

## Setup

1. Public reads work without a token. A token is required to create an issue or to read a private repository.
2. Fine-grained token: https://github.com/settings/personal-access-tokens/new. Grant the one repository Contents (read), Issues (read and write) and Pull requests (read).
3. Classic token: https://github.com/settings/tokens/new. The public_repo scope covers public repositories. Use repo only for private ones.
4. Paste the token as a bearer connection. The header is Authorization.
5. OAuth app: https://github.com/settings/developers. Callback is this platform's service-connection callback. Scope public_repo.
6. Creating an issue or a comment asks for approval.

## Scopes

- `public_repo`

## Settings

- None.

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `github_list_repos` | List repositories | R0 | List public repositories for a user. |
| `github_list_issues` | List issues | R0 | List issues on a repository. |
| `github_list_pulls` | List pull requests | R0 | List pull requests on a repository. |
| `github_read_file` | Read a file | R0 | Read a file from a repository. |
| `github_create_issue` | Create an issue | W2 | Open an issue. |
| `github_comment` | Comment on an issue | W2 | Add a comment to an issue. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
