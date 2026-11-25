# Embed the chat

A workspace administrator creates a widget on the **Channels** screen: its name, the
agent it talks to, and the exact origins of the pages allowed to show it. The screen
gives a script tag:

```html
<script src="{{BASE_URL}}/widget.js" data-integration="<widget id>"></script>
```

The script adds a button that opens the chat in a frame.

## Signing visitors in

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
