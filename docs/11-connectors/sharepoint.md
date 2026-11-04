# SharePoint and OneDrive

Search, list, download and upload files in the signed-in OneDrive.

**Category:** Files
**Auth:** oauth_authorization_code, bearer
**Verification:** Not live-tested
**Note:** Implemented from Microsoft Graph drive docs. No drive was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade

## Setup

1. Register an app in Entra: https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade.
2. Delegated Graph permission Files.Read is enough for search, list and download.
3. Add Files.ReadWrite only if the agent should upload. offline_access lets the token refresh.
4. Create a client secret and set the redirect URI to this platform's callback.
5. An upload asks for approval. The path is inside the signed-in user's drive.

## Scopes

- `Files.Read`
- `Files.ReadWrite`
- `offline_access`

## Settings

- None.

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `sharepoint_search` | Search files | R0 | Search the signed-in drive. |
| `sharepoint_list` | List files | R0 | List files in the drive root. |
| `sharepoint_download` | Download a file | R0 | Download a file's content. |
| `sharepoint_upload` | Upload a file | W2 | Upload a text file to the drive root. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
