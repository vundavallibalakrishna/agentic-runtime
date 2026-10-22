"""Install artefacts for Slack and Teams. Spec: docs/03-specs/16-channels.md §5."""

import io
import zipfile

_SCOPES = (
    "app_mentions:read",
    "chat:write",
    "files:read",
    "files:write",
    "im:history",
    "im:read",
    "im:write",
    "users:read",
    "users:read.email",
    "commands",
    "channels:history",
    "groups:history",
)
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def slack_manifest(name: str, public_url: str, command: str = "/agent") -> str:
    """YAML an admin can import into a Slack app."""
    base = public_url.rstrip("/")
    scopes = "\n".join(f"      - {scope}" for scope in _SCOPES)
    return (
        "display_information:\n"
        f"  name: {name}\n"
        "features:\n"
        "  bot_user:\n"
        f"    display_name: {name}\n"
        "  slash_commands:\n"
        f"    - command: {command}\n"
        f"      url: {base}/channels/slack/commands\n"
        "      description: Ask an agent\n"
        "oauth_config:\n"
        "  scopes:\n"
        "    bot:\n"
        f"{scopes}\n"
        "settings:\n"
        "  event_subscriptions:\n"
        f"    request_url: {base}/channels/slack/events\n"
        "    bot_events:\n"
        "      - app_mention\n"
        "      - message.im\n"
        "  interactivity:\n"
        f"    request_url: {base}/channels/slack/interactions\n"
        "  socket_mode_enabled: false\n"
    )


def teams_package(name: str, app_id: str) -> bytes:
    """Zip with manifest.json and the two icon files Teams asks for."""
    manifest = (
        "{\n"
        f'  "id": "{app_id}",\n'
        f'  "name": {{"short": "{name}", "full": "{name}"}},\n'
        '  "description": {"short": "Ask an agent", "full": "Ask an agent in this workspace."},\n'
        '  "icons": {"color": "color.png", "outline": "outline.png"},\n'
        '  "bots": [{"botId": "' + app_id + '", "scopes": ["personal", "team", "groupChat"]}],\n'
        '  "validDomains": []\n'
        "}\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", manifest)
        archive.writestr("color.png", _PNG)
        archive.writestr("outline.png", _PNG)
    return buffer.getvalue()
