# Outlook

List, read and send Outlook mail for the signed-in mailbox.

**Implementation:** Built
**Category:** Communication
**Auth:** oauth_authorization_code, bearer
**Verification:** Not live-tested
**Note:** Checked against a recorded Microsoft Graph mail example. No mailbox was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://entra.microsoft.com/

## Setup

1. Register an app in Entra.
2. Add delegated permissions Mail.ReadWrite, Mail.Send and offline_access.
3. A bearer token you already hold can be pasted instead of completing OAuth.
4. Sending a message asks for approval.

## Scopes

- `Mail.ReadWrite`
- `Mail.Send`
- `offline_access`

## Tools

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `outlook_list` | List messages | R0 | List recent messages. |
| `outlook_read` | Read a message | R0 | Read one message. |
| `outlook_send` | Send a message | W2 | Send a message. |

Proof label: `unit`. A live call belongs in `scripts/certify_live.sh`.
