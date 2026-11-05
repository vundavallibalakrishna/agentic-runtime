# Slack

List channels, read a channel, post a message and search.

**Implementation:** Built
**Category:** Communication
**Auth:** bearer, oauth_authorization_code
**Verification:** Not live-tested
**Note:** Implemented from Slack's Web API docs. No workspace was connected.
**Local rate limit:** 40 calls a minute.
**Provider page:** https://api.slack.com/apps

## Setup

1. Open https://api.slack.com/apps and choose Create New App, then From scratch.
2. Under OAuth & Permissions, add bot token scopes channels:read, channels:history, groups:read, groups:history and chat:write.
3. Search uses a user token. Add the user scope search:read on the same page.
4. Install the app to the workspace and copy the Bot User OAuth Token. It starts with xoxb-.
5. Invite the bot to each channel it should read. A post asks for approval.
6. For OAuth, set the redirect URL to this platform's service-connection callback and use the same scopes.

## Scopes

- `channels:read`
- `channels:history`
- `groups:read`
- `groups:history`
- `chat:write`
- `search:read`

## Settings

- None.

## Tools

Reads run. Writes (`W2`) wait for approval.

| Tool | Title | Risk | What it does |
|---|---|---|---|
| `slack_list_channels` | List channels | R0 | List channels the token can see. |
| `slack_read_channel` | Read a channel | R0 | Read recent messages in one channel. |
| `slack_post_message` | Post a message | W2 | Post a message to a channel. |
| `slack_search` | Search messages | R0 | Search messages the token can read. |

A 401 tells the person to reconnect. A 403 names the missing permission. A 404 says the item was not found. A 429 includes the provider's retry-after value. List calls follow the provider's next page and stop after three pages or 50 items.
