# PHP and CMS sites

How to put the chat on a site built with a PHP content system. The files named here are
in the repository under `integrations/php/`.

First create the widget on the workspace's **Channels** screen and add your site's origin
(for example `https://www.example.com`, with no path) to its allowed origins. Note the
widget id from the script tag it gives.

## A widget open to anyone

The script tag is all a page needs. Where it goes:

| System | Where to put the script tag |
|---|---|
| WordPress | Install the plugin below; or add the tag to the theme's footer; or a Custom HTML block on one page |
| Drupal | A custom block with full HTML, placed in the footer region; or the theme's `html.html.twig` before `</body>` |
| Joomla | A Custom module with the editor set to none, in a footer position; or the template's `index.php` before `</body>` |
| Any PHP page | Print it before `</body>` |

```php
<script src="{{BASE_URL}}/widget.js" data-integration="<?= htmlspecialchars($widgetId) ?>" defer></script>
```

A site that sends a `Content-Security-Policy` header must allow `{{BASE_URL}}` in
`script-src` and `frame-src`.

## A widget for people signed in to your site

The page also needs a token for the person, signed on your server with the widget's
signing secret. The person's email must belong to a user of the workspace.

`integrations/php/widget-token.php` has one function, with no dependencies:

```php
require __DIR__ . '/widget-token.php';

// An endpoint on your site that only a signed-in person can reach.
header('Content-Type: application/json');
header('Cache-Control: no-store');
echo json_encode(['token' => cura_widget_token(
    getenv('CURA_WIDGET_ID'),
    getenv('CURA_WIDGET_SECRET'),   // never sent to the browser
    $currentUser->email,
    $currentUser->name
)]);
```

And on the page, after the script tag:

```html
<script>
window.addEventListener("ar-widget:token-request", async (event) => {
  const reply = await fetch("/chat-token.php", { credentials: "same-origin" });
  event.detail.respond((await reply.json()).token);
});
</script>
```

The token is good for five minutes by default and ten at most. The widget asks again when
it needs a new one.

## WordPress

`integrations/php/wordpress/cura-works-chat/` is a plugin. Copy the folder into
`wp-content/plugins/`, activate **Cura Works Chat**, and open **Settings → Cura Works
Chat**:

| Setting | Value |
|---|---|
| Workspace address | `{{BASE_URL}}` |
| Widget id | from the script tag |
| Where it shows | every page, or only where the `[cura_chat]` shortcode is placed |
| Who can chat | tick for a widget set to "People your portal has signed in" |
| Host signing secret | the widget's secret, for signed-in chat only. It is stored on your server and never printed back |

For signed-in chat the plugin adds a token endpoint that only a signed-in WordPress user
can call, and the person's WordPress email must match a user of the workspace.

## Calling the API from PHP

Chat, files and knowledge bases are plain HTTPS calls. From PHP, with a service-account
key kept on the server:

```php
$ch = curl_init('{{BASE_URL}}/api/v1/knowledge/search');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        'Authorization: Bearer ' . getenv('CURA_KEY'),
        'Content-Type: application/json',
    ],
    CURLOPT_POSTFIELDS => json_encode(['query' => 'opening hours', 'topK' => 5]),
]);
$hits = json_decode(curl_exec($ch), true)['hits'] ?? [];
```

Never put a key in a page, a theme file a browser can read, or JavaScript. See
[Connect your platform](connect-your-platform.md) for every call.
