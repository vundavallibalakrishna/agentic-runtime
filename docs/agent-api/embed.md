# Embed the chat

A workspace administrator creates a widget on the **Channels** screen: its name, the
agent it talks to, who can chat, and the exact origins of the pages allowed to show it.
The screen gives a script tag to paste into the page:

```html
<script src="{{BASE_URL}}/widget.js" data-integration="<widget id>" defer></script>
```

The script adds a button that opens the chat in a frame. `data-label` sets the button's
text. For WordPress, Drupal, Joomla and plain PHP, see [PHP and CMS sites](php-cms.md).

A widget is one of two kinds.

## Anyone who visits the site

Nobody signs in and the page needs nothing but the script tag. Each visitor gets a chat of
their own that nobody else can open, and cannot attach files.

Three things must be true before a visitor can chat:

1. The widget's **Who can chat** is "Anyone who visits the site".
2. It names the **account visitors act as**: an active user of the workspace. Visitors can
   do only what that account can, so give it nothing but the right to chat and to read
   what the agent answers from.
3. The agent is **opened to visitors**: on the agent's Expose tab, "Let people who have
   not signed in chat with this agent", then publish. In a definition file this is
   `channels.public: true`. A widget cannot open an agent whose owner has not.

### What protects a public chat

Anyone can reach a public chat, including a script. These bound what it can use:

| Setting on the widget | Default | What it bounds |
|---|---|---|
| Allowed origins | none | The pages that may show the chat. A browser refuses any other page. |
| Messages in one chat (`maxMessages`) | 30 | How much one visitor's session can send. Starting a new conversation does not reset it. |
| Characters in one message (`maxMessageChars`) | 2000 | The size, and so the cost, of one message. |
| New chats a minute, in all (`sessionsPerMinute`) | 60 | The whole widget, whoever is asking. |
| New chats a minute, one visitor (`sessionsPerClientPerMinute`) | 10 | One address. |
| Minutes a chat stays open (`sessionSeconds`) | 30 | How long a session lasts. |
| What visitors are told first (`notice`) | empty | Shown with a Start chat button before anything is sent. |

And outside the widget:

- **The agent's budget** caps the steps, tokens and cost of each answer.
- **A quota on the account visitors act as** (Quotas screen) is the ceiling for the whole
  month, whatever the traffic.
- **What the agent can reach.** A visitor can ask it anything. Give a public agent only
  knowledge that is public and tools that are safe for anyone to trigger.
- **Turning it off.** Disabling the widget, or clearing the agent's "opened to visitors",
  stops new chats at once.

A limit that is reached answers `429` with words the visitor can read.

**Behind a proxy.** One visitor is told from another by address. The web app and any
ingress in front of the API must be named in `AR_TRUSTED_PROXY_CIDRS`, or every visitor
looks like the proxy and shares one allowance. A caller that is not a trusted proxy is
counted as itself, whatever `X-Forwarded-For` it sends.

## People your site has signed in

Each person must be a user of the workspace. Your server signs a short-lived token (ten
minutes at most) and your page hands it over when the widget asks:

```javascript
window.addEventListener("ar-widget:token-request", async (event) => {
  const { token } = await fetch("/my-backend/widget-token").then((r) => r.json());
  event.detail.respond(token);
});
```

The token is a JWT signed with the widget's secret (HS256) or your own key (RS256, with
a registered JWKS address). Claims: `sub` (the person's email), `name`, `exp`, and `aud`
set to `ar-widget:<widget id>`. The secret stays on your server.

A person in the widget reaches only the conversation started in that session and only
the agents the widget lists.

## The calls the widget makes

You do not call these yourself; they are listed so a firewall or a reviewer knows them.
All are under `{{BASE_URL}}/api/v1/widget`.

| Call | What it does |
|---|---|
| `GET /api/v1/widget/integrations/{integration_id}` | The widget's name, allowed origins, kind and notice. Public. |
| `POST /api/v1/widget/sessions` | Starts a session: with a token for a signed-in person, with none for a public widget. Sets a cookie scoped to the widget's own path. |
| `GET /api/v1/widget/session` | The agents this session may talk to. |
| `POST /api/v1/widget/conversations` | Starts the session's conversation. |
| `POST /api/v1/widget/conversations/{conversation_id}/messages` | Sends a message. |
| `GET /api/v1/widget/runs/{run_id}/events` | The reply as it is written. |
