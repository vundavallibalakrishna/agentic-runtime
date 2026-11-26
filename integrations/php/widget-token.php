<?php
/**
 * Signs the short-lived token a chat widget asks for, for a person your site has signed in.
 *
 * Only a widget whose visitors are signed in needs this. A widget open to anyone needs
 * no token: the script tag alone is enough.
 *
 * The secret is the widget's "Host signing secret". Keep it on the server (an environment
 * variable, or your CMS's own settings). It must never be sent to the browser.
 */

declare(strict_types=1);

/**
 * @param string $integrationId The widget's id, from the script tag.
 * @param string $secret        The widget's signing secret.
 * @param string $email         The email of the signed-in person. They must be a user of the workspace.
 * @param string $name          The name to show for them.
 * @param int    $ttl           Seconds the token is good for. At most 600.
 */
function cura_widget_token(string $integrationId, string $secret, string $email, string $name, int $ttl = 300): string
{
    $encode = static fn (string $bytes): string => rtrim(strtr(base64_encode($bytes), '+/', '-_'), '=');
    $head = $encode(json_encode(['alg' => 'HS256', 'typ' => 'JWT'], JSON_THROW_ON_ERROR));
    $body = $encode(json_encode([
        'sub' => strtolower($email),
        'name' => $name,
        'aud' => 'ar-widget:' . $integrationId,
        'exp' => time() + max(1, min($ttl, 600)),
    ], JSON_THROW_ON_ERROR));
    $signature = $encode(hash_hmac('sha256', $head . '.' . $body, $secret, true));

    return $head . '.' . $body . '.' . $signature;
}
