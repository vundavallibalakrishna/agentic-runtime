# Email

Send and read mail through the customer's SMTP and IMAP servers.

**Implementation:** Built
**Category:** Communication
**Auth:** basic
**Verification:** Live-tested
**Note:** Send was proven through a local SMTP server started for this milestone, not a customer mailbox. Read was proven against a local IMAP stand-in.
**Local rate limit:** 20 calls a minute.
**Provider page:** https://support.google.com/accounts/answer/185833

## Setup

1. This connector uses the mailbox you name. The platform does not run a mail server.
2. Create an app password if the account uses multi-factor sign-in. Google: https://myaccount.google.com/apppasswords. Microsoft: https://account.microsoft.com/security.
3. Enter the SMTP host and port (usually 587 with TLS) and the IMAP host and port (usually 993 with SSL).
4. The username is the full address. The password is stored as basic auth and is not shown again.
5. Set the From address to that mailbox. A send asks for approval before it leaves.

## Scopes

- A key or password, not an OAuth scope.

## Settings

- SMTP host (`smtpHost`)
- SMTP port (`smtpPort`)
- IMAP host (`imapHost`)
- IMAP port (`imapPort`)
- From address (`fromAddress`)
- SMTP TLS (true or false) (`smtpTls`)
- IMAP SSL (true or false) (`imapSsl`)

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `email_send` | Send email | W2 | Send one message through the customer's SMTP server. |
| `email_list` | List email | R0 | List recent messages in a mailbox. |
| `email_read` | Read email | R0 | Read one message by its id. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
