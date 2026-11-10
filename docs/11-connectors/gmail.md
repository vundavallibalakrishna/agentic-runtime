# Gmail

List, read and send messages for the signed-in mailbox.

**Implementation:** Built
**Category:** Communication
**Auth:** oauth_authorization_code, bearer
**Verification:** Not live-tested
**Note:** Checked against a recorded Gmail API example. No Google account was connected.
**Local rate limit:** 30 calls a minute.
**Provider page:** https://console.cloud.google.com/apis/credentials

## Setup

1. Enable the Gmail API.
2. Create a Web OAuth client and set this platform's callback as a redirect URI.
3. The scope is `https://www.googleapis.com/auth/gmail.modify`.
4. A bearer token you already hold can be pasted instead of completing OAuth.
5. Sending a message asks for approval.

## Scopes

- `https://www.googleapis.com/auth/gmail.modify`

## Tools

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `gmail_list` | List messages | R0 | List messages in the mailbox. |
| `gmail_read` | Read a message | R0 | Read one message. |
| `gmail_send` | Send a message | W2 | Send a message. |

Proof label: `unit` until a recorded provider call promotes it. A live call belongs in `scripts/certify_live.sh` on a machine that holds the token.
