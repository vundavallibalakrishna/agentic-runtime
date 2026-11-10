"""Gmail, Outlook and a generic REST connector. Proof stays contract until a live key is set."""

# ruff: noqa: E501, S105

from __future__ import annotations

from ar_domain.connectors.catalog import ConnectorDef, FieldDef, ToolDef, _tool

_READ = "R0"
_WRITE = "W2"
_GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_MS_AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_MS_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_MS_APP = "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"


def stage11_definitions() -> list[tuple[ConnectorDef, tuple[ToolDef, ...]]]:
    return [_gmail(), _outlook(), _rest()]


def _gmail() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="gmail",
        name="Gmail",
        category="Communication",
        summary="List, read and send Gmail messages for the signed-in mailbox.",
        auth_kind="oauth_authorization_code",
        auth_kinds=("oauth_authorization_code", "bearer"),
        scopes=("https://www.googleapis.com/auth/gmail.modify",),
        registration_url="https://console.cloud.google.com/apis/credentials",
        authorize_url=_GOOGLE_AUTH,
        token_url=_GOOGLE_TOKEN,
        steps=(
            "Enable the Gmail API at https://console.cloud.google.com/apis/library/gmail.googleapis.com.",
            "Create a Web OAuth client and set this platform's callback as a redirect URI.",
            "The scope is https://www.googleapis.com/auth/gmail.modify so the agent can read and send.",
            "A bearer token you already hold can be pasted instead of completing OAuth.",
            "Sending a message asks for approval. The token is stored for this tenant and refreshed.",
        ),
        verification="not_live",
        verification_note=(
            "Checked against a recorded Gmail API example. No Google account was connected."
        ),
        rate_per_minute=30,
        base_url="https://gmail.googleapis.com",
        probe_method="GET",
        probe_path="/gmail/v1/users/me/profile",
        docs="docs/11-connectors/gmail.md",
        tools=(),
    )
    tools: tuple[ToolDef, ...] = (
        _tool(
            "list",
            "List messages",
            "List messages in the signed-in mailbox.",
            _READ,
            "GET",
            "/gmail/v1/users/me/messages",
            query=("q", "maxResults"),
        ),
        _tool(
            "read",
            "Read a message",
            "Read one message by its id.",
            _READ,
            "GET",
            "/gmail/v1/users/me/messages/{id}",
            required=("id",),
        ),
        _tool(
            "send",
            "Send a message",
            "Send a message from the signed-in mailbox.",
            _WRITE,
            "POST",
            "/gmail/v1/users/me/messages/send",
            body=("to", "subject", "text"),
            required=("to", "subject", "text"),
        ),
    )
    return connector, tools


def _outlook() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="outlook",
        name="Outlook",
        category="Communication",
        summary="List, read and send Outlook mail for the signed-in mailbox.",
        auth_kind="oauth_authorization_code",
        auth_kinds=("oauth_authorization_code", "bearer"),
        scopes=("Mail.ReadWrite", "Mail.Send", "offline_access"),
        registration_url=_MS_APP,
        authorize_url=_MS_AUTH,
        token_url=_MS_TOKEN,
        steps=(
            "Register an app in Entra and add delegated Graph permissions Mail.ReadWrite, Mail.Send and offline_access.",
            "Create a client secret and set the redirect URI to this platform's callback.",
            "A bearer token you already hold can be pasted instead of completing OAuth.",
            "Sending a message asks for approval. The refresh token is stored for this tenant.",
        ),
        verification="not_live",
        verification_note=(
            "Checked against a recorded Microsoft Graph mail example. No mailbox was connected."
        ),
        rate_per_minute=30,
        base_url="https://graph.microsoft.com/v1.0",
        probe_method="GET",
        probe_path="/me",
        docs="docs/11-connectors/outlook.md",
        prefix="outlook",
        tools=(),
    )
    tools = (
        _tool(
            "list",
            "List messages",
            "List recent messages in the signed-in mailbox.",
            _READ,
            "GET",
            "/me/messages",
            query=("$top",),
        ),
        _tool(
            "read",
            "Read a message",
            "Read one message by its id.",
            _READ,
            "GET",
            "/me/messages/{id}",
            required=("id",),
        ),
        _tool(
            "send",
            "Send a message",
            "Send a message from the signed-in mailbox.",
            _WRITE,
            "POST",
            "/me/sendMail",
            body=("to", "subject", "text"),
            required=("to", "subject", "text"),
        ),
    )
    return connector, tools


def _rest() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="rest",
        name="REST API",
        category="Developer",
        summary="Call a REST API the tenant names, with a bearer token or an API key.",
        auth_kind="bearer",
        auth_kinds=("bearer", "api_key", "oauth_authorization_code"),
        scopes=("api",),
        registration_url="https://swagger.io/specification/",
        authorize_url="",
        token_url="",
        steps=(
            "Set the API base URL. Paths are appended to it.",
            "Store a bearer token or an API key. It is not shown again.",
            "OAuth uses the authorize and token URLs you enter on the connection.",
            "A POST asks for approval. The response is the provider's JSON.",
        ),
        verification="not_live",
        verification_note=("Checked against a recorded HTTP example. No customer API was called."),
        rate_per_minute=60,
        base_url="",
        probe_method="GET",
        probe_path="/",
        docs="docs/11-connectors/rest.md",
        fields=(FieldDef("baseUrl", "Base URL", "https://api.example.com"),),
        tools=(),
    )
    tools = (
        _tool(
            "get",
            "GET a path",
            "Send a GET request to a path on the connected API.",
            _READ,
            "GET",
            "/{path}",
            query=("query",),
            required=("path",),
        ),
        _tool(
            "post",
            "POST a path",
            "Send a POST request to a path on the connected API.",
            _WRITE,
            "POST",
            "/{path}",
            body=("body",),
            required=("path",),
        ),
    )
    return connector, tools
