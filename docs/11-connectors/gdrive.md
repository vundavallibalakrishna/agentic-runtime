# Google Drive

Search, list, download and upload files.

**Category:** Files
**Auth:** oauth_authorization_code
**Verification:** Not live-tested
**Note:** Implemented from the Drive API v3 docs. No Drive was connected.
**Local rate limit:** 40 calls a minute.
**Provider page:** https://console.cloud.google.com/apis/credentials

## Setup

1. Enable the Google Drive API at https://console.cloud.google.com/apis/library/drive.googleapis.com.
2. Create a Web OAuth client at https://console.cloud.google.com/apis/credentials and set the redirect URI.
3. Read tools need https://www.googleapis.com/auth/drive.readonly.
4. Upload needs https://www.googleapis.com/auth/drive.file, which only covers files this app creates or the user opens.
5. Grant both only when the agent should upload. An upload asks for approval.

## Scopes

- `https://www.googleapis.com/auth/drive.readonly`
- `https://www.googleapis.com/auth/drive.file`

## Settings

- None.

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `gdrive_search` | Search files | R0 | Search files the account can see. |
| `gdrive_list` | List files | R0 | List files, optionally with a query. |
| `gdrive_download` | Download a file | R0 | Download a file's text. |
| `gdrive_upload` | Upload a file | W2 | Upload a text file. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
