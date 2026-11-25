"""Where a knowledge source's documents come from. Every kind calls the source.

Spec: docs/03-specs/10-knowledge.md §5. A source's ``config`` says where to look and
which stored connection to use. It never holds the documents: nothing here answers
from a list written into the configuration, and a kind that cannot reach its source
says why.

``source`` carries the store it belongs to under ``store``, set by the caller.
"""

import hashlib
import mimetypes
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

from ar_common.errors import ArError
from ar_domain.knowledge.acl import map_external

if TYPE_CHECKING:
    from typing import Any

# Kinds whose documents carry the reader list of the system they came from.
_GRAPH_KINDS = frozenset({"sharepoint", "confluence", "google_drive"})
# The most objects, rows or resources one sync reads from a source.
_MAX_ITEMS = 5000


def list_changes(source: dict[str, object], *, mode: str) -> dict[str, object]:
    """One page of the source's items, read from the source."""
    config = _config(source)
    kind = str(source.get("kind") or "")
    if kind == "web":
        return _web(source, config, mode=mode)
    if kind == "s3":
        return _s3(source, config)
    if kind in _GRAPH_KINDS:
        return _graph(source, config, kind)
    if kind == "database":
        return _rows(source, config)
    if kind == "mcp_resource":
        return _resources(source, config)
    return _nothing()


def check(source: dict[str, object]) -> dict[str, object]:
    """Reach the source and return a sample of at most five items."""
    try:
        page = list_changes(source, mode="incremental")
    except (httpx.HTTPError, ArError, OSError, ValueError) as exc:
        return {"ok": False, "sample": [], "error": str(exc)}
    if page.get("error"):
        return {"ok": False, "sample": [], "error": str(page["error"])}
    items = page["items"] if isinstance(page.get("items"), list) else []
    sample = [
        {"external_id": str(item.get("external_id")), "title": str(item.get("title") or "")}
        for item in items[:5]  # type: ignore[index]
        if isinstance(item, dict)
    ]
    return {"ok": True, "sample": sample, "error": None}


def list_acl_changes(source: dict[str, object]) -> list[dict[str, object]]:
    """The reader list of each item, for the kinds whose source keeps one.

    A kind whose documents take the collection's readers has nothing to report, so its
    documents keep the readers the collection gives them.
    """
    page = list_changes(source, mode="incremental")
    items = page.get("items")
    if not isinstance(items, list):
        return []
    return [
        {"external_id": item.get("external_id"), "acl": item.get("acl") or []}
        for item in items
        if isinstance(item, dict) and item.get("source_acl") is True
    ]


def current_acl(source: dict[str, object], external_id: str) -> list[dict[str, object]] | None:
    """Who the source says may read one item now. None when the kind keeps no reader list.

    An item the source no longer returns has no readers. A source that cannot be reached
    raises, and the caller treats that as a refusal.
    """
    kind = str(source.get("kind") or "")
    if kind not in _GRAPH_KINDS and not (kind == "database" and _config(source).get("aclColumn")):
        return None
    page = list_changes(source, mode="incremental")
    if page.get("error"):
        raise OSError(str(page["error"]))
    items = page.get("items")
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and str(item.get("external_id")) == external_id:
            acl = item.get("acl")
            return [row for row in acl if isinstance(row, dict)] if isinstance(acl, list) else []
    return []


def fetch_bytes(item: dict[str, object]) -> tuple[bytes, str]:
    """The item's bytes: read from the source now, or the text the listing came with."""
    mime = str(item.get("mime_type") or "")
    load = item.get("load")
    if callable(load):
        loaded = load()
        if isinstance(loaded, tuple):
            return bytes(loaded[0]), mime or str(loaded[1])
        return bytes(loaded), mime or "application/octet-stream"
    if isinstance(item.get("text"), str):
        return str(item["text"]).encode(), mime or "text/markdown"
    url = str(item.get("uri") or "")
    if url.startswith("http"):
        from ar_common.egress_http import guard, sync_client  # noqa: PLC0415

        problem = guard(url, _hosts(item))
        if problem is not None:
            raise httpx.HTTPError(problem)
        with sync_client(allow=_hosts(item), timeout=5.0, follow_redirects=False) as client:
            response = client.get(url)
        response.raise_for_status()
        return response.content, mime or "text/html"
    return b"", mime or "text/plain"


def map_item_acl(item: dict[str, object], store: Any) -> tuple[list[str], int]:
    from ar_domain.knowledge.access import emails  # noqa: PLC0415

    external = item.get("acl")
    if not isinstance(external, list):
        return [], 0
    groups = getattr(store, "group_keys", {})
    domains = set(getattr(store, "company_domains", {"dev.local"}))
    return map_external(
        [row for row in external if isinstance(row, dict)],
        email_to_user=emails(store),
        group_keys={str(key): str(value) for key, value in groups.items()},
        company_domains=domains,
    )


def _config(source: dict[str, object]) -> dict[str, object]:
    config = source.get("config")
    return config if isinstance(config, dict) else {}


def _hosts(row: dict[str, object]) -> list[str]:
    """Tenant allowlist carried on the source. A source allowlist is not a grant."""
    from ar_domain.egress import tenant_hosts  # noqa: PLC0415

    store = row.get("store")
    tenant = row.get("tenant_id")
    if store is None:
        return []
    return tenant_hosts(store, tenant)


def _web(  # noqa: PLR0911
    source: dict[str, object], config: dict[str, object], *, mode: str
) -> dict[str, object]:
    start = str(config.get("url") or "")
    if not start:
        return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
    allow = (
        {str(item) for item in config.get("allowlist", [])}  # type: ignore[attr-defined]
        if isinstance(config.get("allowlist"), list)
        else set()
    )
    host = urlparse(start).hostname or ""
    if allow and host not in allow and urlparse(start).netloc not in allow:
        return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
    from ar_common import robots  # noqa: PLC0415
    from ar_common.egress_http import guard, sync_client, user_agent  # noqa: PLC0415

    hosts = _hosts(source)
    if guard(start, hosts) is not None:
        return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
    if str(config.get("proxy") or "").strip():
        return {
            "items": [],
            "deleted_external_ids": [],
            "next_cursor": {},
            "done": True,
            "error": "a proxy is configured and is refused",
        }
    client = sync_client(allow=hosts, timeout=5.0, follow_redirects=False)
    try:
        answer = client.get(robots.address(start))
        rules = robots.Robots(robots.text_for(answer.status_code, answer.text), user_agent())
        if not rules.allows(start):
            return {
                "items": [],
                "deleted_external_ids": [],
                "next_cursor": {},
                "done": True,
                "error": "the site's robots.txt asks automated readers not to fetch this page",
            }
        # The validator the last sync was answered with is on the source's cursor. A full
        # sync reads the page whatever the site says about it.
        cursor = source.get("cursor")
        kept = dict(cursor) if isinstance(cursor, dict) else {}
        etag = str(kept.get("etag") or "") if mode != "full" else ""
        page = client.get(start, headers={"If-None-Match": etag} if etag else {})
    finally:
        client.close()
    if page.status_code == 304:
        return {"items": [], "deleted_external_ids": [], "next_cursor": kept, "done": True}
    digest = hashlib.sha256(page.content).hexdigest()
    measured = {
        "status": page.status_code,
        "etag": page.headers.get("etag", ""),
        "lastModified": page.headers.get("last-modified", ""),
    }
    return {
        "items": [
            {
                "external_id": start,
                "title": host or "Page",
                "uri": start,
                "mime_type": "text/html",
                "version_hint": page.headers.get("etag") or digest,
                "measured": measured,
                "text": page.text,
                "acl": [],
            }
        ],
        "deleted_external_ids": [],
        "next_cursor": {"etag": page.headers.get("etag", ""), "sha256": digest},
        "done": True,
    }


def _nothing(error: str = "") -> dict[str, object]:
    page: dict[str, object] = {
        "items": [],
        "deleted_external_ids": [],
        "next_cursor": {},
        "done": True,
    }
    if error:
        page["error"] = error
    return page


def _owner(source: dict[str, object]) -> object:
    """The person whose stored connections the source may use: the one who made it."""
    return source.get("created_by")


def _s3(source: dict[str, object], config: dict[str, object]) -> dict[str, object]:
    """``ListObjectsV2`` on the bucket. Each object is read when it is ingested."""
    from ar_domain.connectors import storage  # noqa: PLC0415
    from ar_domain.tools.service_connections import account_for  # noqa: PLC0415

    store = source.get("store")
    bucket = str(config.get("bucket") or "").strip()
    name = str(config.get("connection") or "").strip()
    if not bucket or not name:
        return _nothing(
            "An S3 source needs a bucket and the name of a stored connection that holds "
            "the access key and secret key."
        )
    try:
        _headers, access_key, secret_key = account_for(
            store, source.get("tenant_id"), _owner(source), name
        )
    except ArError as exc:
        return _nothing(str(exc))
    settings = {
        "endpoint": str(config.get("endpoint") or ""),
        "region": str(config.get("region") or "us-east-1"),
        "bucket": bucket,
        "access_key": access_key,
        "secret_key": secret_key,
    }
    prefix = str(config.get("prefix") or "")
    try:
        rows, whole = storage.list_keys(store, settings, prefix=prefix, limit=_MAX_ITEMS)
    except OSError as exc:
        return _nothing(str(exc))

    def reader(key: str) -> Any:
        return lambda: storage.read_object(store, settings, key=key)

    items = [
        {
            "external_id": str(row["key"]),
            "title": str(row["key"]).rsplit("/", 1)[-1] or str(row["key"]),
            "uri": f"s3://{bucket}/{row['key']}",
            "mime_type": mimetypes.guess_type(str(row["key"]))[0] or "application/octet-stream",
            "version_hint": str(row.get("etag") or ""),
            "load": reader(str(row["key"])),
            "acl": [],
        }
        for row in rows
        if not str(row["key"]).endswith("/")
    ]
    return {
        "items": items,
        "deleted_external_ids": [],
        "next_cursor": {},
        "done": True,
        # A whole listing shows what is gone: a document whose key is no longer listed.
        "complete": whole,
    }


def _rows(source: dict[str, object], config: dict[str, object]) -> dict[str, object]:
    """One read-only query on a data connection. Each row is a document."""
    from ar_domain.tools.database import dispatch_data  # noqa: PLC0415

    store = source.get("store")
    connection = str(source.get("data_connection_id") or config.get("connection") or "").strip()
    query = str(config.get("query") or "").strip()
    if not connection or not query:
        return _nothing(
            "A database source needs a data connection and a query. The query returns one "
            "row for each document."
        )
    answer = dispatch_data(
        store,
        "query",
        {"_tenant_id": source.get("tenant_id"), "connection": connection, "sql": query},
    )
    if answer.get("is_error"):
        return _nothing(str(answer.get("text") or "the query failed"))
    found = answer.get("structured")
    body = found if isinstance(found, dict) else {}
    columns = [str(item) for item in body.get("columns") or []]
    id_column = str(config.get("idColumn") or "id")
    if id_column not in columns:
        return _nothing(
            f"The query returns no column named {id_column}. Name the column that identifies "
            "a row in idColumn."
        )
    title_column = str(config.get("titleColumn") or "title")
    text_column = str(config.get("textColumn") or "text")
    acl_column = str(config.get("aclColumn") or "")
    version_column = str(config.get("versionColumn") or "")
    items: list[dict[str, object]] = []
    for raw in body.get("rows") or []:
        if not isinstance(raw, list):
            continue
        row = dict(zip(columns, raw, strict=False))
        external = str(row.get(id_column))
        if text_column in row:
            text = str(row.get(text_column) or "")
        else:
            text = "\n".join(f"{name}: {row[name]}" for name in columns if name != acl_column)
        item: dict[str, object] = {
            "external_id": external,
            "title": str(row.get(title_column) or external),
            "uri": external,
            "mime_type": "text/markdown",
            "version_hint": str(row.get(version_column) or "") if version_column else "",
            "text": text,
            "acl": _readers(row.get(acl_column)) if acl_column else [],
        }
        if acl_column:
            item["source_acl"] = True
        items.append(item)
    return {
        "items": items,
        "deleted_external_ids": [],
        "next_cursor": {},
        "done": True,
        "complete": not body.get("truncated"),
    }


def _readers(value: object) -> list[dict[str, object]]:
    """An ``acl`` cell (an array, or names separated by commas) as external principals."""
    if isinstance(value, list):
        names = [str(item).strip() for item in value]
    else:
        names = [part.strip() for part in str(value or "").strip("{}").split(",")]
    readers: list[dict[str, object]] = []
    for name in names:
        cleaned = name.strip('"')
        if not cleaned:
            continue
        if "@" in cleaned:
            readers.append({"type": "user", "email": cleaned})
        else:
            readers.append({"type": "group", "name": cleaned})
    return readers


def _resources(  # noqa: PLR0911
    source: dict[str, object], config: dict[str, object]
) -> dict[str, object]:
    """``resources/list`` on a registered MCP server. Each resource is read when ingested."""
    from ar_domain.tools.remote_mcp import RemoteError, list_resources  # noqa: PLC0415
    from ar_domain.tools.service_connections import headers_for  # noqa: PLC0415

    store = source.get("store")
    slug = str(config.get("server") or "").strip()
    if not slug:
        return _nothing("An MCP resource source needs the name of a registered tool server.")
    version = _server_version(store, source.get("tenant_id"), slug)
    if version is None:
        return _nothing(f"No approved tool server named {slug} is registered in this workspace.")
    endpoint = str(version.get("endpoint_url") or "")
    if not endpoint.startswith(("https://", "http://")):
        return _nothing(f"The tool server {slug} is not a remote MCP server.")
    settings = version.get("config")
    server_config = settings if isinstance(settings, dict) else {}
    name = str(config.get("connection") or server_config.get("connection") or "").strip()
    headers: dict[str, str] | None = None
    if name:
        try:
            headers, _secret = headers_for(store, source.get("tenant_id"), _owner(source), name)
        except ArError as exc:
            return _nothing(str(exc))
    elif str(version.get("auth_mode") or "none") != "none":
        return _nothing(
            f"The tool server {slug} signs each person in. A knowledge source reads as one "
            "account: name a stored connection for it."
        )
    try:
        rows, read = list_resources(
            store,
            endpoint,
            headers=headers,
            transport=str(server_config.get("transport") or "streamable"),
        )
    except RemoteError as exc:
        return _nothing(exc.reason)

    def reader(uri: str) -> Any:
        def load() -> tuple[bytes, str]:
            try:
                return read(uri)
            except RemoteError as exc:
                raise OSError(exc.reason) from exc

        return load

    items = [
        {
            "external_id": str(row["uri"]),
            "title": str(row.get("title") or row.get("name") or row["uri"]),
            "uri": str(row["uri"]),
            "mime_type": str(row.get("mimeType") or ""),
            "version_hint": "",
            "load": reader(str(row["uri"])),
            "acl": [],
        }
        for row in rows[:_MAX_ITEMS]
        if row.get("uri")
    ]
    return {
        "items": items,
        "deleted_external_ids": [],
        "next_cursor": {},
        "done": True,
        "complete": len(rows) <= _MAX_ITEMS,
    }


def _server_version(store: Any, tenant_id: object, slug: str) -> dict[str, object] | None:
    """The current version of the tenant's approved server with this name."""
    servers = getattr(store, "tool_servers", None)
    versions = getattr(store, "tool_server_versions", None)
    if not isinstance(servers, dict) or not isinstance(versions, dict):
        return None
    for row in servers.values():
        if (
            isinstance(row, dict)
            and row.get("slug") == slug
            and row.get("tenant_id") == tenant_id
            and row.get("status") == "approved"
            and row.get("disabled_at") is None
        ):
            found = versions.get(row.get("current_version_id"))
            return found if isinstance(found, dict) else None
    return None


def _graph(source: dict[str, object], config: dict[str, object], kind: str) -> dict[str, object]:
    url = str(config.get("url") or "")
    if not url:
        return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
    from ar_common.egress_http import guard, sync_client  # noqa: PLC0415

    hosts = _hosts(source)
    if guard(url, hosts) is not None:
        return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
    # The credential is a stored connection the source names. It is never in the config.
    headers: dict[str, str] = {}
    name = str(config.get("connection") or "").strip()
    if name:
        from ar_domain.tools.service_connections import headers_for  # noqa: PLC0415

        try:
            headers, _secret = headers_for(
                source.get("store"), source.get("tenant_id"), _owner(source), name
            )
        except ArError as exc:
            return _nothing(str(exc))
    with sync_client(allow=hosts, timeout=5.0) as client:
        response = client.get(url, headers=headers)
    response.raise_for_status()
    body = response.json()
    rows = body.get("value") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        rows = body.get("results") if isinstance(body, dict) else []
    items = []
    deleted: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        if row.get("deleted"):
            deleted.append(str(row.get("id") or row.get("external_id")))
            continue
        items.append({**_normalise(row, kind), "source_acl": True})
    return {"items": items, "deleted_external_ids": deleted, "next_cursor": {}, "done": True}


def _normalise(row: dict[str, object], kind: str) -> dict[str, object]:
    external = str(row.get("id") or row.get("external_id") or row.get("name") or kind)
    return {
        "external_id": external,
        "title": str(row.get("title") or row.get("name") or external),
        "uri": str(row.get("uri") or row.get("webUrl") or external),
        "mime_type": str(row.get("mime_type") or "text/markdown"),
        "version_hint": str(row.get("etag") or row.get("version") or row.get("version_hint") or ""),
        "text": str(row.get("text") or row.get("body") or row.get("title") or ""),
        "acl": row.get("acl") or row.get("permissions") or [],
    }
