<?php
/**
 * Plugin Name: Cura Works Chat
 * Description: Adds a Cura Works chat widget to every page, or where the [cura_chat] shortcode is placed.
 * Version: 1.0.0
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 */

declare(strict_types=1);

if (!defined('ABSPATH')) {
    exit;
}

const CURA_CHAT_OPTIONS = 'cura_chat_options';

/** The settings an administrator saved, with every key present. */
function cura_chat_options(): array
{
    $saved = get_option(CURA_CHAT_OPTIONS, []);

    return wp_parse_args(is_array($saved) ? $saved : [], [
        'base_url' => '',
        'integration_id' => '',
        'label' => '',
        'placement' => 'all',
        'signed' => '0',
        'secret' => '',
    ]);
}

/** Whether the widget has what it needs to load. */
function cura_chat_ready(array $options): bool
{
    return (bool) preg_match('#^https://[^\s/]+#i', $options['base_url'])
        && (bool) preg_match('/^[0-9a-f-]{36}$/i', $options['integration_id']);
}

/** Prints the widget's script tag once on a page. */
function cura_chat_print(): void
{
    static $printed = false;
    $options = cura_chat_options();
    if ($printed || !cura_chat_ready($options)) {
        return;
    }
    $printed = true;
    printf(
        '<script src="%s/widget.js" data-integration="%s"%s defer></script>' . "\n",
        esc_url(untrailingslashit($options['base_url'])),
        esc_attr($options['integration_id']),
        $options['label'] !== '' ? ' data-label="' . esc_attr($options['label']) . '"' : ''
    );
    if ($options['signed'] === '1' && is_user_logged_in()) {
        // The widget asks the page for a token; the page gets one from this site's server.
        printf(
            "<script>window.addEventListener('ar-widget:token-request',function(e){fetch(%s,{credentials:'same-origin',headers:{'X-WP-Nonce':%s}}).then(function(r){return r.json()}).then(function(d){if(d&&d.token)e.detail.respond(d.token)})});</script>\n",
            wp_json_encode(rest_url('cura-chat/v1/token')),
            wp_json_encode(wp_create_nonce('wp_rest'))
        );
    }
}

add_action('wp_footer', static function (): void {
    if (cura_chat_options()['placement'] === 'all') {
        cura_chat_print();
    }
});

add_shortcode('cura_chat', static function (): string {
    ob_start();
    cura_chat_print();

    return (string) ob_get_clean();
});

/** A token for the person signed in to WordPress. The signing secret never leaves the server. */
add_action('rest_api_init', static function (): void {
    register_rest_route('cura-chat/v1', '/token', [
        'methods' => 'GET',
        'permission_callback' => static fn (): bool => is_user_logged_in(),
        'callback' => static function () {
            $options = cura_chat_options();
            $user = wp_get_current_user();
            if ($options['signed'] !== '1' || $options['secret'] === '' || !cura_chat_ready($options)) {
                return new WP_Error('cura_chat_off', 'Signed chat is not set up.', ['status' => 404]);
            }
            $encode = static fn (string $bytes): string => rtrim(strtr(base64_encode($bytes), '+/', '-_'), '=');
            $head = $encode(wp_json_encode(['alg' => 'HS256', 'typ' => 'JWT']));
            $body = $encode(wp_json_encode([
                'sub' => strtolower($user->user_email),
                'name' => $user->display_name,
                'aud' => 'ar-widget:' . $options['integration_id'],
                'exp' => time() + 300,
            ]));
            $signature = $encode(hash_hmac('sha256', $head . '.' . $body, $options['secret'], true));
            $response = new WP_REST_Response(['token' => $head . '.' . $body . '.' . $signature]);
            $response->header('Cache-Control', 'no-store');

            return $response;
        },
    ]);
});

add_action('admin_init', static function (): void {
    register_setting('cura_chat', CURA_CHAT_OPTIONS, [
        'type' => 'array',
        'sanitize_callback' => static function ($input): array {
            $input = is_array($input) ? $input : [];
            $before = cura_chat_options();
            $secret = isset($input['secret']) ? trim((string) $input['secret']) : '';

            return [
                'base_url' => esc_url_raw(trim((string) ($input['base_url'] ?? '')), ['https']),
                'integration_id' => sanitize_text_field((string) ($input['integration_id'] ?? '')),
                'label' => sanitize_text_field((string) ($input['label'] ?? '')),
                'placement' => ($input['placement'] ?? 'all') === 'shortcode' ? 'shortcode' : 'all',
                'signed' => empty($input['signed']) ? '0' : '1',
                // An empty field keeps the secret already saved: it is never printed back.
                'secret' => $secret !== '' ? $secret : $before['secret'],
            ];
        },
    ]);
});

add_action('admin_menu', static function (): void {
    add_options_page('Cura Works Chat', 'Cura Works Chat', 'manage_options', 'cura-chat', static function (): void {
        $options = cura_chat_options();
        $name = CURA_CHAT_OPTIONS;
        ?>
        <div class="wrap">
            <h1>Cura Works Chat</h1>
            <form method="post" action="options.php">
                <?php settings_fields('cura_chat'); ?>
                <table class="form-table" role="presentation">
                    <tr>
                        <th scope="row"><label for="cura-base">Workspace address</label></th>
                        <td><input id="cura-base" class="regular-text" type="url" name="<?php echo esc_attr($name); ?>[base_url]" value="<?php echo esc_attr($options['base_url']); ?>" placeholder="https://workspace.example.com"></td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="cura-id">Widget id</label></th>
                        <td><input id="cura-id" class="regular-text" type="text" name="<?php echo esc_attr($name); ?>[integration_id]" value="<?php echo esc_attr($options['integration_id']); ?>">
                        <p class="description">From the script tag the Channels screen gives: the value of data-integration.</p></td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="cura-label">Button text</label></th>
                        <td><input id="cura-label" class="regular-text" type="text" name="<?php echo esc_attr($name); ?>[label]" value="<?php echo esc_attr($options['label']); ?>"></td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="cura-place">Where it shows</label></th>
                        <td><select id="cura-place" name="<?php echo esc_attr($name); ?>[placement]">
                            <option value="all" <?php selected($options['placement'], 'all'); ?>>On every page</option>
                            <option value="shortcode" <?php selected($options['placement'], 'shortcode'); ?>>Only where [cura_chat] is placed</option>
                        </select></td>
                    </tr>
                    <tr>
                        <th scope="row">Who can chat</th>
                        <td><label><input type="checkbox" name="<?php echo esc_attr($name); ?>[signed]" value="1" <?php checked($options['signed'], '1'); ?>> Only people signed in to this site (the widget is set to "People your portal has signed in")</label></td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="cura-secret">Host signing secret</label></th>
                        <td><input id="cura-secret" class="regular-text" type="password" autocomplete="new-password" name="<?php echo esc_attr($name); ?>[secret]" value="" placeholder="<?php echo $options['secret'] !== '' ? 'Saved. Type to replace.' : ''; ?>">
                        <p class="description">Needed only for signed-in chat. It stays on this server.</p></td>
                    </tr>
                </table>
                <?php submit_button(); ?>
            </form>
        </div>
        <?php
    });
});
