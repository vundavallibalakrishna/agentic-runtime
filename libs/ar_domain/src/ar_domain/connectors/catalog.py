"""Connector catalogue. Each row is a definition, not a live account.

``implementation`` is ``built`` when the tools and setup steps ship in the product.
Verification is one of ``live``, ``public`` or ``not_live``. ``not_live`` means the
tools were checked against recorded provider examples and have not been called
on a customer account. A recorded M36 canary can promote that label to ``live``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

_READ = "R0"
_WRITE = "W2"


@dataclass(frozen=True, slots=True)
class ToolDef:
    """One tool a person can turn on or off."""

    name: str
    title: str
    description: str
    risk: str
    method: str
    path: str
    query: tuple[str, ...] = ()
    body: tuple[str, ...] = ()
    page: str = "none"
    required: tuple[str, ...] = ()
    kind: str = "http"


@dataclass(frozen=True, slots=True)
class FieldDef:
    """A non-secret setting the install form asks for."""

    name: str
    label: str
    placeholder: str = ""


@dataclass(frozen=True, slots=True)
class ConnectorDef:
    """One product a customer can connect."""

    slug: str
    name: str
    category: str
    summary: str
    auth_kind: str
    auth_kinds: tuple[str, ...]
    scopes: tuple[str, ...]
    registration_url: str
    authorize_url: str
    token_url: str
    steps: tuple[str, ...]
    verification: str
    verification_note: str
    rate_per_minute: int
    base_url: str
    probe_method: str
    probe_path: str
    docs: str
    tools: tuple[ToolDef, ...]
    fields: tuple[FieldDef, ...] = ()
    allows_anonymous: bool = False
    prefix: str = ""
    implementation: str = "built"

    def tool_prefix(self) -> str:
        return self.prefix or self.slug.replace("-", "")


def _tool(
    name: str,
    title: str,
    description: str,
    risk: str,
    method: str,
    path: str,
    *,
    query: tuple[str, ...] = (),
    body: tuple[str, ...] = (),
    page: str = "none",
    required: tuple[str, ...] = (),
    kind: str = "http",
) -> ToolDef:
    return ToolDef(
        name=name,
        title=title,
        description=description,
        risk=risk,
        method=method,
        path=path,
        query=query,
        body=body,
        page=page,
        required=required,
        kind=kind,
    )


def _prefix(connector: ConnectorDef, tools: Iterable[ToolDef]) -> tuple[ToolDef, ...]:
    head = connector.tool_prefix()
    return tuple(
        ToolDef(
            name=f"{head}_{tool.name}",
            title=tool.title,
            description=tool.description,
            risk=tool.risk,
            method=tool.method,
            path=tool.path,
            query=tool.query,
            body=tool.body,
            page=tool.page,
            required=tool.required,
            kind=tool.kind,
        )
        for tool in tools
    )


_GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_MS_AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_MS_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_MS_APP = "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"
_ATLASSIAN_APPS = "https://developer.atlassian.com/console/myapps/"
_ATLASSIAN_AUTH = "https://auth.atlassian.com/authorize"
_ATLASSIAN_TOKEN = "https://auth.atlassian.com/oauth/token"


def _build() -> tuple[ConnectorDef, ...]:
    email = ConnectorDef(
        slug="email",
        name="Email",
        category="Communication",
        summary="Send and read mail through the customer's SMTP and IMAP servers.",
        auth_kind="basic",
        auth_kinds=("basic",),
        scopes=(),
        registration_url="https://support.google.com/accounts/answer/185833",
        authorize_url="",
        token_url="",
        steps=(
            "This connector uses the mailbox you name. The platform does not run a mail server.",
            "Create an app password if the account uses multi-factor sign-in. Google: https://myaccount.google.com/apppasswords. Microsoft: https://account.microsoft.com/security.",
            "Enter the SMTP host and port (usually 587 with TLS) and the IMAP host and port (usually 993 with SSL).",
            "The username is the full address. The password is stored as basic auth and is not shown again.",
            "Set the From address to that mailbox. A send asks for approval before it leaves.",
        ),
        verification="live",
        verification_note=(
            "Send was proven through a local SMTP server started for this milestone, "
            "not a customer mailbox. Read was proven against a local IMAP stand-in."
        ),
        rate_per_minute=20,
        base_url="",
        probe_method="SMTP",
        probe_path="",
        docs="docs/11-connectors/email.md",
        fields=(
            FieldDef("smtpHost", "SMTP host", "smtp.example.com"),
            FieldDef("smtpPort", "SMTP port", "587"),
            FieldDef("imapHost", "IMAP host", "imap.example.com"),
            FieldDef("imapPort", "IMAP port", "993"),
            FieldDef("fromAddress", "From address", "you@example.com"),
            FieldDef("smtpTls", "SMTP TLS (true or false)", "true"),
            FieldDef("imapSsl", "IMAP SSL (true or false)", "true"),
        ),
        tools=(),
    )
    slack = ConnectorDef(
        slug="slack",
        name="Slack",
        category="Communication",
        summary="List channels, read a channel, post a message and search.",
        auth_kind="bearer",
        auth_kinds=("bearer", "oauth_authorization_code"),
        scopes=(
            "channels:read",
            "channels:history",
            "groups:read",
            "groups:history",
            "chat:write",
            "search:read",
        ),
        registration_url="https://api.slack.com/apps",
        authorize_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        steps=(
            "Open https://api.slack.com/apps and choose Create New App, then From scratch.",
            "Under OAuth & Permissions, add bot token scopes channels:read, channels:history, groups:read, groups:history and chat:write.",
            "Search uses a user token. Add the user scope search:read on the same page.",
            "Install the app to the workspace and copy the Bot User OAuth Token. It starts with xoxb-.",
            "Invite the bot to each channel it should read. A post asks for approval.",
            "For OAuth, set the redirect URL to this platform's service-connection callback and use the same scopes.",
        ),
        verification="not_live",
        verification_note="Implemented from Slack's Web API docs. No workspace was connected.",
        rate_per_minute=40,
        base_url="https://slack.com/api",
        probe_method="GET",
        probe_path="/auth.test",
        docs="docs/11-connectors/slack.md",
        tools=(),
    )
    teams = ConnectorDef(
        slug="teams",
        name="Microsoft Teams",
        category="Communication",
        summary="List channels in a team and post a message.",
        auth_kind="oauth_authorization_code",
        auth_kinds=("oauth_authorization_code", "bearer"),
        scopes=("Channel.ReadBasic.All", "ChannelMessage.Send", "offline_access"),
        registration_url=_MS_APP,
        authorize_url=_MS_AUTH,
        token_url=_MS_TOKEN,
        steps=(
            "Open Entra app registrations: https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade.",
            "New registration. Platform is Web. Redirect URI is this platform's service-connection callback.",
            "API permissions, Microsoft Graph, delegated: Channel.ReadBasic.All, ChannelMessage.Send and offline_access.",
            "Grant admin consent when the tenant requires it.",
            "Certificates & secrets, New client secret. Put the application id in Client id and the secret in the connection.",
            "The built read lists channels in a team. It does not read message text. The team id is the id in the Teams link.",
            "A channel post asks for approval.",
        ),
        verification="not_live",
        verification_note="Implemented from Microsoft Graph docs. No tenant was connected.",
        rate_per_minute=30,
        base_url="https://graph.microsoft.com/v1.0",
        probe_method="GET",
        probe_path="/me",
        docs="docs/11-connectors/teams.md",
        tools=(),
    )
    gcal = ConnectorDef(
        slug="gcal",
        name="Google Calendar",
        category="Calendar",
        summary="List events, find free time and create an event.",
        auth_kind="oauth_authorization_code",
        auth_kinds=("oauth_authorization_code", "bearer"),
        scopes=(
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/calendar.freebusy",
        ),
        registration_url="https://console.cloud.google.com/apis/credentials",
        authorize_url=_GOOGLE_AUTH,
        token_url=_GOOGLE_TOKEN,
        steps=(
            "Open https://console.cloud.google.com/apis/library/calendar-json.googleapis.com and enable the Google Calendar API.",
            "Configure the OAuth consent screen, then open https://console.cloud.google.com/apis/credentials.",
            "Create an OAuth client ID of type Web application. Add this platform's callback as an authorized redirect URI.",
            "Scopes: https://www.googleapis.com/auth/calendar.events and https://www.googleapis.com/auth/calendar.freebusy.",
            "Put the client id and client secret on the connection. Creating an event asks for approval.",
            "A bearer token you already hold can be pasted instead of completing OAuth. It is not shown again.",
            "Calendar id defaults to primary, which is the signed-in calendar.",
        ),
        verification="not_live",
        verification_note="Implemented from the Calendar API docs. No Google account was connected.",
        rate_per_minute=40,
        base_url="https://www.googleapis.com/calendar/v3",
        probe_method="GET",
        probe_path="/users/me/calendarList",
        docs="docs/11-connectors/gcal.md",
        tools=(),
    )
    m365 = ConnectorDef(
        slug="m365-calendar",
        name="Microsoft 365 Calendar",
        category="Calendar",
        summary="List events, find free time and create an event on Microsoft 365.",
        auth_kind="oauth_authorization_code",
        auth_kinds=("oauth_authorization_code", "bearer"),
        scopes=("Calendars.ReadWrite", "offline_access"),
        registration_url=_MS_APP,
        authorize_url=_MS_AUTH,
        token_url=_MS_TOKEN,
        steps=(
            "Open the same Entra app page as Teams: https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade.",
            "Add delegated Microsoft Graph permissions Calendars.ReadWrite and offline_access. Admin consent if required.",
            "Create a client secret. The authorize URL is https://login.microsoftonline.com/common/oauth2/v2.0/authorize.",
            "The token URL is https://login.microsoftonline.com/common/oauth2/v2.0/token.",
            "Creating an event asks for approval. Times are sent in UTC.",
        ),
        verification="not_live",
        verification_note="Implemented from Microsoft Graph calendar docs. No mailbox was connected.",
        rate_per_minute=30,
        base_url="https://graph.microsoft.com/v1.0",
        probe_method="GET",
        probe_path="/me/calendar",
        docs="docs/11-connectors/m365-calendar.md",
        prefix="m365cal",
        tools=(),
    )
    drive = ConnectorDef(
        slug="gdrive",
        name="Google Drive",
        category="Files",
        summary="Search, list, download and upload files.",
        auth_kind="oauth_authorization_code",
        auth_kinds=("oauth_authorization_code", "bearer"),
        scopes=(
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.file",
        ),
        registration_url="https://console.cloud.google.com/apis/credentials",
        authorize_url=_GOOGLE_AUTH,
        token_url=_GOOGLE_TOKEN,
        steps=(
            "Enable the Google Drive API at https://console.cloud.google.com/apis/library/drive.googleapis.com.",
            "Create a Web OAuth client at https://console.cloud.google.com/apis/credentials and set the redirect URI.",
            "Read tools need https://www.googleapis.com/auth/drive.readonly.",
            "Upload needs https://www.googleapis.com/auth/drive.file, which only covers files this app creates or the user opens.",
            "Grant both only when the agent should upload. An upload asks for approval.",
            "A bearer token you already hold can be pasted instead of completing OAuth. It is not shown again.",
        ),
        verification="not_live",
        verification_note="Implemented from the Drive API v3 docs. No Drive was connected.",
        rate_per_minute=40,
        base_url="https://www.googleapis.com/drive/v3",
        probe_method="GET",
        probe_path="/about",
        docs="docs/11-connectors/gdrive.md",
        tools=(),
    )
    share = ConnectorDef(
        slug="sharepoint",
        name="SharePoint and OneDrive",
        category="Files",
        summary="Search, list, download and upload files in the signed-in OneDrive.",
        auth_kind="oauth_authorization_code",
        auth_kinds=("oauth_authorization_code", "bearer"),
        scopes=("Files.Read", "Files.ReadWrite", "offline_access"),
        registration_url=_MS_APP,
        authorize_url=_MS_AUTH,
        token_url=_MS_TOKEN,
        steps=(
            "Register an app in Entra: https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade.",
            "Delegated Graph permission Files.Read is enough for search, list and download.",
            "Add Files.ReadWrite only if the agent should upload. offline_access lets the token refresh.",
            "Create a client secret and set the redirect URI to this platform's callback.",
            "These tools call the signed-in OneDrive (/me/drive). They do not take a SharePoint site id.",
            "An upload asks for approval. The path is inside the signed-in user's drive.",
        ),
        verification="not_live",
        verification_note="Implemented from Microsoft Graph drive docs. No drive was connected.",
        rate_per_minute=30,
        base_url="https://graph.microsoft.com/v1.0",
        probe_method="GET",
        probe_path="/me/drive",
        docs="docs/11-connectors/sharepoint.md",
        tools=(),
    )
    s3 = ConnectorDef(
        slug="s3",
        name="S3-compatible storage",
        category="Files",
        summary="List, get and put objects on S3 or a compatible endpoint.",
        auth_kind="basic",
        auth_kinds=("basic",),
        scopes=("s3:ListBucket", "s3:GetObject", "s3:PutObject"),
        registration_url="https://console.aws.amazon.com/iam/home#/users",
        authorize_url="",
        token_url="",
        steps=(
            "On AWS, open https://console.aws.amazon.com/iam/home#/users and create a user, not the account root.",
            "Attach a policy limited to one bucket: s3:ListBucket, s3:GetObject and s3:PutObject.",
            "Create an access key. The username on the connection is the access key id. The secret is the secret key.",
            "Set the region. Leave the endpoint empty for AWS, or set it for MinIO or another compatible service.",
            "A put asks for approval. The bucket name is a setting, not a secret.",
        ),
        verification="public",
        verification_note=(
            "Proven against SeaweedFS, an S3-compatible reference server run for this milestone. "
            "The MinIO image could not be pulled. Not AWS."
        ),
        rate_per_minute=60,
        base_url="",
        probe_method="LIST",
        probe_path="",
        docs="docs/11-connectors/s3.md",
        fields=(
            FieldDef("endpoint", "Endpoint URL", "http://127.0.0.1:9000"),
            FieldDef("region", "Region", "us-east-1"),
            FieldDef("bucket", "Bucket", "documents"),
        ),
        tools=(),
    )
    jira = ConnectorDef(
        slug="jira",
        name="Jira",
        category="Work",
        summary="Search issues, create and update an issue, and add a comment.",
        auth_kind="basic",
        auth_kinds=("basic", "oauth_authorization_code"),
        scopes=("read:jira-work", "write:jira-work"),
        registration_url=_ATLASSIAN_APPS,
        authorize_url=_ATLASSIAN_AUTH,
        token_url=_ATLASSIAN_TOKEN,
        steps=(
            "For an API token, open https://id.atlassian.com/manage-profile/security/api-tokens and create a token.",
            "Basic auth uses the Atlassian account email as the username and the token as the secret.",
            "Set the site URL, for example https://your-site.atlassian.net.",
            "For OAuth, create an app at https://developer.atlassian.com/console/myapps/ with Jira scopes read:jira-work and write:jira-work.",
            "Authorize URL https://auth.atlassian.com/authorize. Token URL https://auth.atlassian.com/oauth/token.",
            "Creating, updating and commenting ask for approval.",
        ),
        verification="not_live",
        verification_note="Implemented from the Jira Cloud REST v3 examples. No site was connected.",
        rate_per_minute=30,
        base_url="",
        probe_method="GET",
        probe_path="/rest/api/3/myself",
        docs="docs/11-connectors/jira.md",
        fields=(FieldDef("baseUrl", "Site URL", "https://your-site.atlassian.net"),),
        tools=(),
    )
    github = ConnectorDef(
        slug="github",
        name="GitHub",
        category="Work",
        summary="List repositories, issues and pull requests, read a file, open an issue and comment.",
        auth_kind="bearer",
        auth_kinds=("bearer", "oauth_authorization_code"),
        scopes=("public_repo",),
        registration_url="https://github.com/settings/tokens/new",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        steps=(
            "Public reads work without a token. A token is required to create an issue or to read a private repository.",
            "Fine-grained token: https://github.com/settings/personal-access-tokens/new. Grant the one repository Contents (read), Issues (read and write) and Pull requests (read).",
            "Classic token: https://github.com/settings/tokens/new. The public_repo scope covers public repositories. Use repo only for private ones.",
            "Paste the token as a bearer connection. The header is Authorization.",
            "OAuth app: https://github.com/settings/developers. Callback is this platform's service-connection callback. Scope public_repo.",
            "Creating an issue or a comment asks for approval.",
        ),
        verification="live",
        verification_note=(
            "A public read of octocat/Hello-World returned the README heading. "
            "An issue was created on a repository the proof token could write. "
            "That token is not a customer account."
        ),
        rate_per_minute=30,
        base_url="https://api.github.com",
        probe_method="GET",
        probe_path="/rate_limit",
        docs="docs/11-connectors/github.md",
        allows_anonymous=True,
        tools=(),
    )
    confluence = ConnectorDef(
        slug="confluence",
        name="Confluence",
        category="Work",
        summary="Search, read a page, and create or update a page.",
        auth_kind="basic",
        auth_kinds=("basic", "oauth_authorization_code"),
        scopes=("read:confluence-content.all", "write:confluence-content"),
        registration_url=_ATLASSIAN_APPS,
        authorize_url=_ATLASSIAN_AUTH,
        token_url=_ATLASSIAN_TOKEN,
        steps=(
            "API token: https://id.atlassian.com/manage-profile/security/api-tokens. Username is the account email.",
            "Set the site URL, for example https://your-site.atlassian.net. Cloud paths start with /wiki.",
            "OAuth app: https://developer.atlassian.com/console/myapps/ with Confluence scopes read:confluence-content.all and write:confluence-content.",
            "Writing a page asks for approval. The body is storage format.",
        ),
        verification="not_live",
        verification_note="Implemented from the Confluence Cloud REST examples. No site was connected.",
        rate_per_minute=30,
        base_url="",
        probe_method="GET",
        probe_path="/wiki/rest/api/user/current",
        docs="docs/11-connectors/confluence.md",
        fields=(FieldDef("baseUrl", "Site URL", "https://your-site.atlassian.net"),),
        tools=(),
    )
    notion = ConnectorDef(
        slug="notion",
        name="Notion",
        category="Work",
        summary="Search, read a page or database, and create a page.",
        auth_kind="bearer",
        auth_kinds=("bearer", "oauth_authorization_code"),
        scopes=("Read content", "Update content", "Insert content"),
        registration_url="https://www.notion.so/my-integrations",
        authorize_url="https://api.notion.com/v1/oauth/authorize",
        token_url="https://api.notion.com/v1/oauth/token",
        steps=(
            "Open https://www.notion.so/my-integrations and choose New integration. Type Internal.",
            "Capabilities: Read content for search and read. Insert content to create a page. Update content only if you will edit.",
            "Copy the internal integration secret and store it as a bearer token.",
            "In Notion, open the page or database, then Connections, and add the integration. Unshared pages stay invisible.",
            "A public OAuth integration uses https://api.notion.com/v1/oauth/authorize and https://api.notion.com/v1/oauth/token.",
            "The connector sends Notion-Version 2022-06-28. Creating a page asks for approval.",
        ),
        verification="not_live",
        verification_note="Implemented from the Notion API 2022-06-28 examples. No workspace was connected.",
        rate_per_minute=20,
        base_url="https://api.notion.com/v1",
        probe_method="GET",
        probe_path="/users/me",
        docs="docs/11-connectors/notion.md",
        tools=(),
    )
    raw = (
        (
            email,
            (
                _tool(
                    "send",
                    "Send email",
                    "Send one message through the customer's SMTP server.",
                    _WRITE,
                    "POST",
                    "",
                    required=("to", "subject", "body"),
                    kind="email_send",
                ),
                _tool(
                    "list",
                    "List email",
                    "List recent messages in a mailbox.",
                    _READ,
                    "GET",
                    "",
                    kind="email_list",
                ),
                _tool(
                    "read",
                    "Read email",
                    "Read one message by its id.",
                    _READ,
                    "GET",
                    "",
                    required=("id",),
                    kind="email_read",
                ),
            ),
        ),
        (
            slack,
            (
                _tool(
                    "list_channels",
                    "List channels",
                    "List channels the token can see.",
                    _READ,
                    "GET",
                    "/conversations.list",
                    query=("limit", "cursor"),
                    page="cursor",
                ),
                _tool(
                    "read_channel",
                    "Read a channel",
                    "Read recent messages in one channel.",
                    _READ,
                    "GET",
                    "/conversations.history",
                    query=("channel", "limit", "cursor"),
                    page="cursor",
                    required=("channel",),
                ),
                _tool(
                    "post_message",
                    "Post a message",
                    "Post a message to a channel.",
                    _WRITE,
                    "POST",
                    "/chat.postMessage",
                    body=("channel", "text"),
                    required=("channel", "text"),
                ),
                _tool(
                    "search",
                    "Search messages",
                    "Search messages the token can read.",
                    _READ,
                    "GET",
                    "/search.messages",
                    query=("query", "cursor"),
                    page="cursor",
                    required=("query",),
                ),
            ),
        ),
        (
            teams,
            (
                _tool(
                    "list_channels",
                    "List channels",
                    "List channels in a team.",
                    _READ,
                    "GET",
                    "/teams/{team}/channels",
                    required=("team",),
                ),
                _tool(
                    "post_message",
                    "Post a message",
                    "Post a message to a channel.",
                    _WRITE,
                    "POST",
                    "/teams/{team}/channels/{channel}/messages",
                    body=("content",),
                    required=("team", "channel", "content"),
                ),
            ),
        ),
        (
            gcal,
            (
                _tool(
                    "list_events",
                    "List events",
                    "List events on a calendar.",
                    _READ,
                    "GET",
                    "/calendars/{calendar}/events",
                    query=("timeMin", "pageToken", "maxResults"),
                    page="token",
                ),
                _tool(
                    "find_free",
                    "Find free time",
                    "Find when a calendar is free.",
                    _READ,
                    "POST",
                    "/freeBusy",
                    body=("timeMin", "timeMax", "calendar"),
                    required=("timeMin", "timeMax"),
                ),
                _tool(
                    "create_event",
                    "Create an event",
                    "Create an event on a calendar.",
                    _WRITE,
                    "POST",
                    "/calendars/{calendar}/events",
                    body=("summary", "start", "end"),
                    required=("summary", "start", "end"),
                ),
            ),
        ),
        (
            m365,
            (
                _tool(
                    "list_events",
                    "List events",
                    "List events on the signed-in calendar.",
                    _READ,
                    "GET",
                    "/me/calendarView",
                    query=("startDateTime", "endDateTime"),
                    required=("startDateTime", "endDateTime"),
                ),
                _tool(
                    "find_free",
                    "Find free time",
                    "Find free time for one or more schedules.",
                    _READ,
                    "POST",
                    "/me/calendar/getSchedule",
                    body=("schedules", "start", "end"),
                    required=("schedules", "start", "end"),
                ),
                _tool(
                    "create_event",
                    "Create an event",
                    "Create an event on the signed-in calendar.",
                    _WRITE,
                    "POST",
                    "/me/events",
                    body=("subject", "start", "end"),
                    required=("subject", "start", "end"),
                ),
            ),
        ),
        (
            drive,
            (
                _tool(
                    "search",
                    "Search files",
                    "Search files the account can see.",
                    _READ,
                    "GET",
                    "/files",
                    query=("q", "pageToken", "pageSize"),
                    page="token",
                    required=("q",),
                ),
                _tool(
                    "list",
                    "List files",
                    "List files, optionally with a query.",
                    _READ,
                    "GET",
                    "/files",
                    query=("q", "pageToken", "pageSize"),
                    page="token",
                ),
                _tool(
                    "download",
                    "Download a file",
                    "Download a file's text.",
                    _READ,
                    "GET",
                    "/files/{file_id}",
                    query=("alt",),
                    required=("file_id",),
                ),
                _tool(
                    "upload",
                    "Upload a file",
                    "Upload a text file.",
                    _WRITE,
                    "POST",
                    "/files",
                    body=("name", "text"),
                    required=("name", "text"),
                    kind="gdrive_upload",
                ),
            ),
        ),
        (
            share,
            (
                _tool(
                    "search",
                    "Search files",
                    "Search the signed-in drive.",
                    _READ,
                    "GET",
                    "/me/drive/root/search(q='{query}')",
                    required=("query",),
                ),
                _tool(
                    "list",
                    "List files",
                    "List files in the drive root.",
                    _READ,
                    "GET",
                    "/me/drive/root/children",
                ),
                _tool(
                    "download",
                    "Download a file",
                    "Download a file's content.",
                    _READ,
                    "GET",
                    "/me/drive/items/{item_id}/content",
                    required=("item_id",),
                ),
                _tool(
                    "upload",
                    "Upload a file",
                    "Upload a text file to the drive root.",
                    _WRITE,
                    "PUT",
                    "/me/drive/root:/{path}:/content",
                    body=("text",),
                    required=("path", "text"),
                    kind="sharepoint_upload",
                ),
            ),
        ),
        (
            s3,
            (
                _tool(
                    "list",
                    "List objects",
                    "List objects in the bucket.",
                    _READ,
                    "GET",
                    "",
                    kind="s3_list",
                ),
                _tool(
                    "get",
                    "Get an object",
                    "Read an object's text.",
                    _READ,
                    "GET",
                    "",
                    required=("key",),
                    kind="s3_get",
                ),
                _tool(
                    "put",
                    "Put an object",
                    "Write an object's text.",
                    _WRITE,
                    "PUT",
                    "",
                    required=("key", "text"),
                    kind="s3_put",
                ),
            ),
        ),
        (
            jira,
            (
                _tool(
                    "search",
                    "Search issues",
                    "Search issues with JQL.",
                    _READ,
                    "GET",
                    "/rest/api/3/search/jql",
                    query=("jql", "maxResults", "nextPageToken"),
                    page="token",
                    required=("jql",),
                ),
                _tool(
                    "create_issue",
                    "Create an issue",
                    "Create an issue in a project.",
                    _WRITE,
                    "POST",
                    "/rest/api/3/issue",
                    body=("project", "summary", "description"),
                    required=("project", "summary"),
                ),
                _tool(
                    "update_issue",
                    "Update an issue",
                    "Update an issue's summary or description.",
                    _WRITE,
                    "PUT",
                    "/rest/api/3/issue/{issue}",
                    body=("summary", "description"),
                    required=("issue",),
                ),
                _tool(
                    "add_comment",
                    "Add a comment",
                    "Add a comment to an issue.",
                    _WRITE,
                    "POST",
                    "/rest/api/3/issue/{issue}/comment",
                    body=("body",),
                    required=("issue", "body"),
                ),
            ),
        ),
        (
            github,
            (
                _tool(
                    "list_repos",
                    "List repositories",
                    "List public repositories for a user.",
                    _READ,
                    "GET",
                    "/users/{owner}/repos",
                    query=("per_page", "page"),
                    page="link",
                    required=("owner",),
                ),
                _tool(
                    "list_issues",
                    "List issues",
                    "List issues on a repository.",
                    _READ,
                    "GET",
                    "/repos/{owner}/{repo}/issues",
                    query=("state", "per_page", "page"),
                    page="link",
                    required=("owner", "repo"),
                ),
                _tool(
                    "list_pulls",
                    "List pull requests",
                    "List pull requests on a repository.",
                    _READ,
                    "GET",
                    "/repos/{owner}/{repo}/pulls",
                    query=("state", "per_page", "page"),
                    page="link",
                    required=("owner", "repo"),
                ),
                _tool(
                    "read_file",
                    "Read a file",
                    "Read a file from a repository.",
                    _READ,
                    "GET",
                    "/repos/{owner}/{repo}/contents/{path}",
                    required=("owner", "repo", "path"),
                ),
                _tool(
                    "create_issue",
                    "Create an issue",
                    "Open an issue.",
                    _WRITE,
                    "POST",
                    "/repos/{owner}/{repo}/issues",
                    body=("title", "body"),
                    required=("owner", "repo", "title"),
                ),
                _tool(
                    "comment",
                    "Comment on an issue",
                    "Add a comment to an issue.",
                    _WRITE,
                    "POST",
                    "/repos/{owner}/{repo}/issues/{issue}/comments",
                    body=("body",),
                    required=("owner", "repo", "issue", "body"),
                ),
            ),
        ),
        (
            confluence,
            (
                _tool(
                    "search",
                    "Search pages",
                    "Search pages with CQL.",
                    _READ,
                    "GET",
                    "/wiki/rest/api/search",
                    query=("cql", "limit", "start"),
                    page="offset",
                    required=("cql",),
                ),
                _tool(
                    "read_page",
                    "Read a page",
                    "Read a page, including its storage body.",
                    _READ,
                    "GET",
                    "/wiki/rest/api/content/{page_id}",
                    query=("expand",),
                    required=("page_id",),
                ),
                _tool(
                    "write_page",
                    "Create or update a page",
                    "Create a page, or update one when page_id is set.",
                    _WRITE,
                    "POST",
                    "/wiki/rest/api/content",
                    body=("title", "space", "body", "page_id"),
                    required=("title",),
                    kind="confluence_write",
                ),
            ),
        ),
        (
            notion,
            (
                _tool(
                    "search",
                    "Search",
                    "Search pages and databases shared with the integration.",
                    _READ,
                    "POST",
                    "/search",
                    body=("query",),
                    page="cursor",
                ),
                _tool(
                    "read_page",
                    "Read a page",
                    "Read a page.",
                    _READ,
                    "GET",
                    "/pages/{page_id}",
                    required=("page_id",),
                ),
                _tool(
                    "read_database",
                    "Read a database",
                    "Read a database.",
                    _READ,
                    "GET",
                    "/databases/{database_id}",
                    required=("database_id",),
                ),
                _tool(
                    "create_page",
                    "Create a page",
                    "Create a page under a parent page.",
                    _WRITE,
                    "POST",
                    "/pages",
                    body=("parent", "title"),
                    required=("parent", "title"),
                ),
            ),
        ),
    )
    from ar_domain.connectors.catalog_batch import batch_definitions  # noqa: PLC0415

    rows: list[tuple[ConnectorDef, tuple[ToolDef, ...]]] = list(raw)
    rows.extend(batch_definitions())
    built: list[ConnectorDef] = []
    for connector, tools in rows:
        built.append(
            ConnectorDef(
                slug=connector.slug,
                name=connector.name,
                category=connector.category,
                summary=connector.summary,
                auth_kind=connector.auth_kind,
                auth_kinds=connector.auth_kinds,
                scopes=connector.scopes,
                registration_url=connector.registration_url,
                authorize_url=connector.authorize_url,
                token_url=connector.token_url,
                steps=connector.steps,
                verification=connector.verification,
                verification_note=connector.verification_note,
                rate_per_minute=connector.rate_per_minute,
                base_url=connector.base_url,
                probe_method=connector.probe_method,
                probe_path=connector.probe_path,
                docs=connector.docs,
                tools=_prefix(connector, tools),
                fields=connector.fields,
                allows_anonymous=connector.allows_anonymous,
                prefix=connector.prefix,
                implementation=connector.implementation,
            )
        )
    return tuple(built)


CONNECTORS: tuple[ConnectorDef, ...] = _build()
_BY_SLUG = {item.slug: item for item in CONNECTORS}
_BY_TOOL = {tool.name: (item, tool) for item in CONNECTORS for tool in item.tools}


def connector_by_slug(slug: str) -> ConnectorDef | None:
    return _BY_SLUG.get(slug)


def tool_by_name(name: str) -> tuple[ConnectorDef, ToolDef] | None:
    return _BY_TOOL.get(name)


def categories() -> list[str]:
    found: list[str] = []
    for item in CONNECTORS:
        if item.category not in found:
            found.append(item.category)
    return found


# A description for each parameter a connector tool takes, so the model can fill it
# from its schema alone (M39-T01a). The names are shared across providers (pagination,
# ids, search), so one map covers all 92 tools.
_PARAM_DESCRIPTIONS: dict[str, str] = {
    # Pagination
    "cursor": "Opaque pagination cursor from a previous response; omit for the first page.",
    "after": "Return items after this cursor from a previous response; omit for the first page.",
    "pageToken": "The page token from a previous response; omit for the first page.",
    "nextPageToken": "The page token from a previous response; omit for the first page.",
    "page": "The 1-based page number to return.",
    "limit": "The maximum number of items to return.",
    "maxResults": "The maximum number of results to return.",
    "pageSize": "The maximum number of items per page.",
    "per_page": "The number of items per page.",
    "$top": "The maximum number of items to return (Microsoft Graph $top).",
    "sysparm_limit": "The maximum number of records to return (ServiceNow).",
    "sysparm_offset": "The number of records to skip before returning results (ServiceNow).",
    # Search and selection
    "query": "The search query.",
    "q": "The search query or filter expression.",
    "jql": "A Jira Query Language (JQL) expression selecting issues.",
    "cql": "A Confluence Query Language (CQL) expression selecting content.",
    "sysparm_query": "A ServiceNow encoded query filtering records.",
    "fields": "A comma-separated list of fields to return.",
    "expand": "A comma-separated list of related data to include in the response.",
    # Scope and identity
    "project": "The project id or key.",
    "subscription": "The Azure subscription id.",
    "api-version": "The API version to use for the request.",
    "owner": "The repository owner, a user or organisation.",
    "repo": "The repository name.",
    "group": "The resource group name.",
    "group_id": "The group id.",
    "zone": "The compute zone, for example us-central1-a.",
    "company_id": "The company id.",
    "app_id": "The application id.",
    "team": "The team id or name.",
    "channel": "The channel id or name.",
    "calendar": "The calendar id, or 'primary' for the user's main calendar.",
    "space": "The Confluence space key.",
    "database_id": "The database id.",
    "parent": "The id of the parent resource.",
    "table": "The table name.",
    "object": "The object or resource type to act on.",
    # Ids
    "user_id": "The user id.",
    "page_id": "The page id.",
    "file_id": "The file id.",
    "item_id": "The item id.",
    "record_id": "The record id.",
    "ticket_id": "The ticket id.",
    "contact_id": "The contact id.",
    "sys_id": "The ServiceNow record sys_id.",
    "issue": "The issue number or key.",
    # Content
    "title": "The title.",
    "name": "The name.",
    "summary": "A short summary or title.",
    "description": "The description text.",
    "short_description": "A short, one-line description.",
    "body": "The main body or content of the item.",
    "content": "The content to write.",
    "text": "The message or note text.",
    "comment": "The comment text.",
    "subject": "The subject line.",
    "category": "The category.",
    "state": "The state to set or filter by.",
    "urgency": "The urgency level.",
    "type": "The type.",
    "path": "The resource or file path.",
    "email": "The email address.",
    "firstname": "The first name.",
    "lastname": "The last name.",
    # Time
    "start": "The start, an offset or a start time depending on the tool.",
    "end": "The end, an offset or an end time depending on the tool.",
    "timeMin": "The earliest time to include, as an RFC 3339 timestamp.",
    "timeMax": "The latest time to include, as an RFC 3339 timestamp.",
    "startDateTime": "The start date and time, in ISO 8601.",
    "endDateTime": "The end date and time, in ISO 8601.",
    "schedules": "The mailboxes or resources to query for free/busy.",
    # Misc
    "alt": "The response format, for example 'media' to download file content.",
}


def _describe_param(name: str) -> str:
    """A description for a connector parameter, or a plain fallback for a new one."""
    return _PARAM_DESCRIPTIONS.get(name) or f"The {name.replace('_', ' ')}."


def tool_records() -> list[dict[str, object]]:
    """Registry rows for the built-in connectors server."""
    rows: list[dict[str, object]] = []
    for connector in CONNECTORS:
        for tool in connector.tools:
            properties: dict[str, object] = {}
            for name in (*_path_names(tool.path), *tool.query, *tool.body):
                kind = (
                    "integer"
                    if name
                    in {
                        "limit",
                        "maxResults",
                        "pageSize",
                        "per_page",
                        "sysparm_limit",
                        "sysparm_offset",
                    }
                    else "string"
                )
                properties[name] = {"type": kind, "description": _describe_param(name)}
            properties.setdefault(
                "cursor", {"type": "string", "description": _describe_param("cursor")}
            )
            rows.append(
                {
                    "name": tool.name,
                    "title": tool.title,
                    "description": f"{connector.name}: {tool.description}",
                    "input_schema": {
                        "type": "object",
                        "properties": properties,
                        "required": list(tool.required),
                    },
                    "risk_class": tool.risk,
                    "annotations": {"connector": connector.slug, "readOnlyHint": tool.risk == "R0"},
                }
            )
    return rows


def _path_names(path: str) -> tuple[str, ...]:
    names: list[str] = []
    cursor = 0
    while True:
        start = path.find("{", cursor)
        if start < 0:
            return tuple(names)
        end = path.find("}", start)
        if end < 0:
            return tuple(names)
        names.append(path[start + 1 : end])
        cursor = end + 1
