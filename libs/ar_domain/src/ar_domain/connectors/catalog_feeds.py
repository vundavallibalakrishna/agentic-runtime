# ruff: noqa: E501, S106
"""Authenticated HTTP feeds. The first row is a vendor catalogue entry.

Paths and auth live on the row. Nothing here is a live call: the note says so.
"""

from __future__ import annotations

from ar_domain.connectors.catalog import ConnectorDef, FieldDef, ToolDef, _tool

_READ = "R0"


def feed_definitions() -> list[tuple[ConnectorDef, tuple[ToolDef, ...]]]:
    return [_lexis()]


def _lexis() -> tuple[ConnectorDef, tuple[ToolDef, ...]]:
    connector = ConnectorDef(
        slug="lexisnexis-regulatory",
        name="LexisNexis Regulatory Compliance",
        category="Feeds",
        summary=(
            "Read a subscribed regulatory feed. Not live-tested: the paths are from the "
            "vendor's published API guide and no customer credential was used."
        ),
        auth_kind="token_exchange",
        auth_kinds=("token_exchange",),
        scopes=("feed",),
        registration_url="https://rcapi-plus.lexis.com",
        authorize_url="",
        exchange_user_field="email",
        exchange_secret_field="password",
        exchange_extra_header="customerId",
        token_url="https://rcapi-plus.lexis.com/f/Access/authtoken",
        steps=(
            "Create a service connection of kind token_exchange.",
            "Set tokenUrl to https://rcapi-plus.lexis.com/f/Access/authtoken.",
            "Set username to the API email and the secret to the password. The secret is posted, never put on a query string.",
            "Set header name to token, with no Bearer prefix.",
            "Set the exchange fields to email and password, the extra header to customerId, and client id to the customer id.",
            "Not live-tested. A production call needs the customer's subscription.",
        ),
        verification="not_live",
        verification_note=(
            "Not live-tested. Endpoints are from the vendor's published Regulatory "
            "Compliance API guide (2026). No call was made with a customer credential."
        ),
        rate_per_minute=30,
        base_url="https://rcapi-plus.lexis.com",
        probe_method="GET",
        probe_path="/f/UserSubscription/subscriptions",
        docs="https://rcapi-plus.lexis.com",
        fields=(
            FieldDef("tokenHeader", "Token header", "token"),
            FieldDef("customerId", "Customer id", ""),
        ),
        tools=(),
    )
    tools = (
        _tool(
            "subscriptions",
            "List subscriptions",
            "List the modules this API user may retrieve.",
            _READ,
            "GET",
            "/f/UserSubscription/subscriptions",
        ),
        _tool(
            "contents",
            "List subscribed contents",
            "List subscribed content. type and from_date are the vendor's query parameters, not a platform enum.",
            _READ,
            "GET",
            "/f/SubscribedContents/Contents",
            query=("type", "from_date", "end_date", "page", "items_per_page"),
        ),
        _tool(
            "content",
            "Read one content item",
            "Read one subscribed item.",
            _READ,
            "GET",
            "/f/SubscribedContents/Content",
            query=("id",),
            required=("id",),
        ),
        _tool(
            "mandates",
            "List mandates",
            "List official sources linked to subscribed modules.",
            _READ,
            "GET",
            "/f/Mandates/mandates",
        ),
        _tool(
            "regulators",
            "List regulators",
            "List regulators linked to subscribed modules.",
            _READ,
            "GET",
            "/f/Regulators/regulators",
        ),
        _tool(
            "download",
            "Download a document",
            "Download one document version by its vendor ids.",
            _READ,
            "GET",
            "/f/document/download/{object_pguid}/{version}/{name}",
            required=("object_pguid", "version", "name"),
        ),
    )
    return connector, tools
