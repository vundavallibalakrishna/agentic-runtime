"""Run one connector tool. Writes stay on W2 so the pipeline asks first."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_common.errors import ArError, ErrorCode
from ar_domain.connectors.catalog import CONNECTORS, ToolDef, connector_by_slug, tool_by_name
from ar_domain.connectors.http import probe_http, rate_limited, run_http
from ar_domain.tools.service_connections import account_for

if TYPE_CHECKING:
    from typing import Any


def dispatch_connector(  # noqa: PLR0911
    store: Any, name: str, arguments: dict[str, object]
) -> dict[str, object]:
    found = tool_by_name(name)
    if found is None:
        return _fail("unknown_tool", f"Unknown connector tool {name}.")
    connector, tool = found
    install = _install(store, arguments, connector.slug)
    if install is None:
        return _fail(
            "connector_not_installed",
            f"Install {connector.name} and connect an account before using this tool.",
        )
    disabled = install.get("disabled_tools")
    if isinstance(disabled, list) and name in {str(item) for item in disabled}:
        return _fail(
            "tool_disabled",
            f"{tool.title} is turned off. Enable it on the {connector.name} connector page.",
        )
    limited = rate_limited(
        store, arguments.get("_tenant_id"), connector.slug, connector.rate_per_minute
    )
    if limited:
        return _fail("rate_limited", limited)
    public = {key: value for key, value in arguments.items() if not str(key).startswith("_")}
    try:
        headers, username, secret = _auth(
            store, arguments, install, anonymous=connector.allows_anonymous
        )
    except ArError as exc:
        return _fail("credential_required", f"{exc}. Reconnect the account on the connector page.")
    public = _overlay(tool, install, public)
    if tool.kind == "aws" or connector.slug == "aws":
        from ar_domain.connectors.aws_api import run_aws  # noqa: PLC0415

        return run_aws(store, tool, public, install, username, secret)
    if connector.slug == "gcp":
        minted = _gcp_headers(store, install, secret)
        if minted.get("is_error"):
            return minted
        headers = {"Authorization": f"Bearer {minted['token']}"}
    if tool.kind == "http" or connector.slug == "gcp":
        base = _base(connector, install)
        if not base and not str(tool.path).startswith("http"):
            return _fail(
                "validation_failed", "Set the site URL on the connector before calling it."
            )
        return run_http(store, connector, tool, public, headers, base or "https://invalid.invalid")
    return _special(store, tool, public, install, username, secret, headers)


def probe_install(  # noqa: PLR0911
    store: Any, install: dict[str, object], actor_tenant: object, actor_user: object
) -> dict[str, object]:
    connector = connector_by_slug(str(install.get("slug") or ""))
    if connector is None:
        return {"ok": False, "status": 0, "error": "Unknown connector."}
    arguments = {"_tenant_id": actor_tenant, "_user_id": actor_user}
    try:
        headers, username, secret = _auth(
            store, arguments, install, anonymous=connector.allows_anonymous
        )
    except ArError as exc:
        return {"ok": False, "status": 0, "error": str(exc)}
    if connector.slug == "email":
        return _probe_email(store, install, username, secret)
    if connector.slug == "s3":
        return _probe_s3(store, install, username, secret)
    if connector.slug == "aws":
        from ar_domain.connectors.aws_api import probe_aws  # noqa: PLC0415

        return probe_aws(store, install, username, secret)
    if connector.slug == "gcp":
        minted = _gcp_headers(store, install, secret)
        if minted.get("is_error"):
            return {
                "ok": False,
                "status": 0,
                "error": str(minted.get("text") or "credentials rejected"),
            }
        headers = {"Authorization": f"Bearer {minted['token']}"}
    if connector.slug == "azure":
        subscription = _config(install).get("subscriptionId", "")
        if not subscription:
            return {"ok": False, "status": 0, "error": "Set the subscription id on the connector."}
        return probe_http(
            store,
            connector,
            headers,
            _base(connector, install),
            path=f"/subscriptions/{subscription}?api-version=2022-12-01",
        )
    base = _base(connector, install)
    if not base:
        return {"ok": False, "status": 0, "error": "Set the site URL on the connector first."}
    return probe_http(store, connector, headers, base)


def _special(  # noqa: PLR0911, PLR0917
    store: Any,
    tool: ToolDef,
    arguments: dict[str, object],
    install: dict[str, object],
    username: str,
    secret: str,
    headers: dict[str, str],
) -> dict[str, object]:
    kind = tool.kind
    if kind == "email_send":
        return _email_send(store, install, username, secret, arguments)
    if kind == "email_list":
        return _email_list(store, install, username, secret, arguments)
    if kind == "email_read":
        return _email_read(store, install, username, secret, arguments)
    if kind == "s3_list":
        return _s3(store, install, username, secret, "list", arguments)
    if kind == "s3_get":
        return _s3(store, install, username, secret, "get", arguments)
    if kind == "s3_put":
        return _s3(store, install, username, secret, "put", arguments)
    if kind == "gdrive_upload":
        return _gdrive_upload(store, install, headers, arguments)
    if kind == "sharepoint_upload":
        return _share_upload(store, install, headers, arguments)
    if kind == "confluence_write":
        connector = connector_by_slug("confluence")
        if connector is None:
            return _fail("unknown_tool", "Confluence is not in the catalogue.")
        base = _base(connector, install)
        return run_http(store, connector, tool, arguments, headers, base)
    return _fail("unknown_tool", f"Unknown connector action {kind}.")


def _install(store: Any, arguments: dict[str, object], slug: str) -> dict[str, object] | None:
    book = getattr(store, "connector_installs", None)
    if not isinstance(book, dict):
        return None
    tenant = str(arguments.get("_tenant_id") or "")
    user = str(arguments.get("_user_id") or "")
    for row in book.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("slug")) != slug or str(row.get("status")) != "installed":
            continue
        if str(row.get("tenant_id")) == tenant and str(row.get("owner_user_id")) == user:
            return row
    return None


def _auth(
    store: Any,
    arguments: dict[str, object],
    install: dict[str, object],
    *,
    anonymous: bool,
) -> tuple[dict[str, str], str, str]:
    name = str(install.get("connection_name") or "")
    if not name:
        if anonymous:
            return {}, "", ""
        raise ArError(ErrorCode.FORBIDDEN, "Connect an account on the connector page.")
    return account_for(store, arguments.get("_tenant_id"), arguments.get("_user_id"), name)


_AZURE_VERSION = {
    "azure_list_resources": "2021-04-01",
    "azure_list_resource_groups": "2021-04-01",
    "azure_vm_state": "2023-07-01",
    "azure_list_role_assignments": "2022-04-01",
}


def _overlay(
    tool: ToolDef, install: dict[str, object], arguments: dict[str, object]
) -> dict[str, object]:
    config = _config(install)
    copied = dict(arguments)
    path = tool.path
    if "{subscription}" in path and not copied.get("subscription"):
        copied["subscription"] = config.get("subscriptionId", "")
    if "{project}" in path and not copied.get("project"):
        copied["project"] = config.get("projectId", "")
    if "{zone}" in path and not copied.get("zone"):
        copied["zone"] = config.get("zone") or "us-central1-a"
    if "project" in tool.query and not copied.get("project"):
        copied["project"] = config.get("projectId", "")
    version = _AZURE_VERSION.get(tool.name)
    if version and not copied.get("api-version"):
        copied["api-version"] = version
    return copied


def _gcp_headers(store: Any, install: dict[str, object], secret: str) -> dict[str, object]:
    from ar_domain.connectors.gcp_auth import bearer_for  # noqa: PLC0415

    row = _connection_row(store, install)
    if row is None:
        return _fail("credential_required", "Connect a service account on the connector page.")
    if not row.get("scopes"):
        row["scopes"] = ["https://www.googleapis.com/auth/cloud-platform.read-only"]
    return bearer_for(store, row, secret)


def _connection_row(store: Any, install: dict[str, object]) -> dict[str, object] | None:
    book = getattr(store, "service_connections", None)
    if not isinstance(book, dict):
        return None
    found = book.get(install.get("connection_id"))
    if isinstance(found, dict):
        return found
    name = str(install.get("connection_name") or "")
    for row in book.values():
        if isinstance(row, dict) and str(row.get("name")) == name:
            return row
    return None


def _config(install: dict[str, object]) -> dict[str, str]:
    raw = install.get("config")
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}


def _base(connector: Any, install: dict[str, object]) -> str:
    configured = _config(install).get("baseUrl", "").rstrip("/")
    if configured:
        return configured
    return str(connector.base_url or "").rstrip("/")


def _email_send(
    store: Any,
    install: dict[str, object],
    username: str,
    secret: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    from ar_domain.connectors.mail import send_message  # noqa: PLC0415

    config = _config(install)
    host = config.get("smtpHost", "")
    if not host:
        return _fail("validation_failed", "Set the SMTP host on the connector.")
    sender = config.get("fromAddress") or username
    return send_message(
        store,
        host=host,
        port=_port(config.get("smtpPort"), 587),
        username=username,
        password=secret,
        sender=sender,
        recipient=str(arguments.get("to") or ""),
        subject=str(arguments.get("subject") or ""),
        body=str(arguments.get("body") or ""),
        use_tls=config.get("smtpTls", "true").lower() != "false",
    )


def _email_list(
    store: Any,
    install: dict[str, object],
    username: str,
    secret: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    from ar_domain.connectors.mail import list_messages  # noqa: PLC0415

    config = _config(install)
    host = config.get("imapHost", "")
    if not host:
        return _fail("validation_failed", "Set the IMAP host on the connector.")
    limit = arguments.get("limit")
    count = limit if isinstance(limit, int) else 10
    return list_messages(
        store,
        host=host,
        port=_port(config.get("imapPort"), 993),
        username=username,
        password=secret,
        limit=max(1, min(count, 50)),
        use_ssl=config.get("imapSsl", "true").lower() != "false",
    )


def _email_read(
    store: Any,
    install: dict[str, object],
    username: str,
    secret: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    from ar_domain.connectors.mail import read_message  # noqa: PLC0415

    config = _config(install)
    host = config.get("imapHost", "")
    if not host:
        return _fail("validation_failed", "Set the IMAP host on the connector.")
    return read_message(
        store,
        host=host,
        port=_port(config.get("imapPort"), 993),
        username=username,
        password=secret,
        message_id=str(arguments.get("id") or ""),
        use_ssl=config.get("imapSsl", "true").lower() != "false",
    )


def _s3(  # noqa: PLR0917
    store: Any,
    install: dict[str, object],
    username: str,
    secret: str,
    action: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    from ar_domain.connectors import storage  # noqa: PLC0415

    config = _config(install)
    settings = {
        "endpoint": config.get("endpoint", ""),
        "region": config.get("region", "us-east-1"),
        "bucket": config.get("bucket", ""),
        "access_key": username,
        "secret_key": secret,
    }
    if not settings["bucket"]:
        return _fail("validation_failed", "Set the bucket on the connector.")
    if action == "list":
        return storage.list_objects(store, settings, prefix=str(arguments.get("prefix") or ""))
    key = str(arguments.get("key") or "")
    if not key:
        return _fail("validation_failed", "key is required")
    if action == "get":
        return storage.get_object(store, settings, key=key)
    return storage.put_object(store, settings, key=key, text=str(arguments.get("text") or ""))


def _gdrive_upload(
    store: Any, install: dict[str, object], headers: dict[str, str], arguments: dict[str, object]
) -> dict[str, object]:
    import httpx  # noqa: PLC0415
    import orjson  # noqa: PLC0415

    from ar_domain.connectors.http import explain_status  # noqa: PLC0415
    from ar_domain.tools.http_tools import guard_public  # noqa: PLC0415

    del install
    url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
    problem = guard_public(url, allow=["*"], loopback=True)
    if problem:
        return _fail("egress_denied", problem)
    name = str(arguments.get("name") or "note.txt")
    text = str(arguments.get("text") or "")
    boundary = "ar-connector"
    payload = b"".join(
        [
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode(),
            orjson.dumps({"name": name}),
            f"\r\n--{boundary}\r\nContent-Type: text/plain\r\n\r\n".encode(),
            text.encode(),
            f"\r\n--{boundary}--".encode(),
        ]
    )
    request_headers = {**headers, "Content-Type": f"multipart/related; boundary={boundary}"}
    transport = getattr(store, "connector_transport", None)
    kwargs: dict[str, object] = {"timeout": 20.0, "follow_redirects": False}
    if transport is not None:
        kwargs["transport"] = transport
    try:
        with httpx.Client(**kwargs) as client:  # type: ignore[arg-type]
            response = client.post(url, headers=request_headers, content=payload)
    except httpx.HTTPError:
        return _fail("upstream_error", "The provider did not answer. Check the host and try again.")
    if response.status_code >= 400:
        return _fail("upstream_error", explain_status(response.status_code, response.headers))
    return {"text": f"Uploaded {name}.", "structured": {"name": name}, "is_error": False}


def _share_upload(
    store: Any, install: dict[str, object], headers: dict[str, str], arguments: dict[str, object]
) -> dict[str, object]:
    from urllib.parse import quote  # noqa: PLC0415

    import httpx  # noqa: PLC0415

    from ar_domain.connectors.http import explain_status  # noqa: PLC0415
    from ar_domain.tools.http_tools import guard_public  # noqa: PLC0415

    del install
    path = quote(str(arguments.get("path") or "note.txt"), safe="/")
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{path}:/content"
    problem = guard_public(url, allow=["*"], loopback=True)
    if problem:
        return _fail("egress_denied", problem)
    text = str(arguments.get("text") or "")
    transport = getattr(store, "connector_transport", None)
    kwargs: dict[str, object] = {"timeout": 20.0, "follow_redirects": False}
    if transport is not None:
        kwargs["transport"] = transport
    try:
        with httpx.Client(**kwargs) as client:  # type: ignore[arg-type]
            response = client.put(
                url,
                headers={**headers, "Content-Type": "text/plain"},
                content=text.encode(),
            )
    except httpx.HTTPError:
        return _fail("upstream_error", "The provider did not answer. Check the host and try again.")
    if response.status_code >= 400:
        return _fail("upstream_error", explain_status(response.status_code, response.headers))
    return {"text": f"Uploaded {path}.", "structured": {"path": path}, "is_error": False}


def _probe_email(
    store: Any, install: dict[str, object], username: str, secret: str
) -> dict[str, object]:
    import smtplib  # noqa: PLC0415

    from ar_domain.connectors.mail import host_blocked  # noqa: PLC0415

    config = _config(install)
    host = config.get("smtpHost", "")
    if not host:
        return {"ok": False, "status": 0, "error": "Set the SMTP host on the connector."}
    problem = host_blocked(host)
    if problem:
        return {"ok": False, "status": 0, "error": problem}
    port = _port(config.get("smtpPort"), 587)
    try:
        with smtplib.SMTP(host, port, timeout=15) as client:
            client.ehlo()
            if config.get("smtpTls", "true").lower() != "false":
                client.starttls()
                client.ehlo()
            if username:
                client.login(username, secret)
    except (OSError, smtplib.SMTPException) as exc:
        return {
            "ok": False,
            "status": 0,
            "error": f"SMTP refused the connection. {exc.__class__.__name__}.",
        }
    del store
    return {"ok": True, "status": 0, "error": None}


def _probe_s3(
    store: Any, install: dict[str, object], username: str, secret: str
) -> dict[str, object]:
    result = _s3(store, install, username, secret, "list", {})
    if result.get("is_error"):
        return {"ok": False, "status": 0, "error": str(result.get("text") or "")}
    return {"ok": True, "status": 200, "error": None}


def _port(value: str | None, default: int) -> int:
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _fail(code: str, text: str) -> dict[str, object]:
    return {"text": text, "structured": {}, "is_error": True, "code": code}


def catalogue_slugs() -> list[str]:
    return [item.slug for item in CONNECTORS]
