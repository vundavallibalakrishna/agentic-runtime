"""Connector change detection shared by the dev API and the ingest worker.

Spec: docs/03-specs/10-knowledge.md §5. HTTP calls go out only when a source
config names a base URL. Recorded fixtures and the seeded SharePoint stub pass
items in ``config`` instead.
"""

import hashlib
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

import httpx

from ar_domain.knowledge.acl import map_external

if TYPE_CHECKING:
    from typing import Any


def list_changes(source: dict[str, object], *, mode: str) -> dict[str, object]:  # noqa: PLR0911
    """Return one page of source items. Config fixtures win over the network."""
    config = _config(source)
    items = config.get("items")
    if isinstance(items, list):
        deleted = config.get("deleted_external_ids")
        return {
            "items": [item for item in items if isinstance(item, dict)],
            "deleted_external_ids": list(deleted) if isinstance(deleted, list) else [],
            "next_cursor": {"page": 1},
            "done": True,
        }
    kind = str(source.get("kind") or "")
    if kind == "web":
        return _web(config)
    if kind == "s3":
        return _s3(config)
    if kind == "sharepoint":
        return _graph(config, "sharepoint")
    if kind == "confluence":
        return _graph(config, "confluence")
    if kind == "google_drive":
        return _graph(config, "google_drive")
    if kind == "database":
        return _rows(config)
    if kind == "mcp_resource":
        return _resources(config)
    del mode
    return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}


def check(source: dict[str, object]) -> dict[str, object]:
    """Credentials and a sample of at most five items."""
    try:
        page = list_changes(source, mode="incremental")
    except httpx.HTTPError as exc:
        return {"ok": False, "sample": [], "error": str(exc)}
    items = page["items"] if isinstance(page.get("items"), list) else []
    sample = [
        {"external_id": str(item.get("external_id")), "title": str(item.get("title") or "")}
        for item in items[:5]  # type: ignore[index]
        if isinstance(item, dict)
    ]
    return {"ok": True, "sample": sample, "error": None}


def list_acl_changes(source: dict[str, object]) -> list[dict[str, object]]:
    config = _config(source)
    changes = config.get("acl_changes")
    if isinstance(changes, list):
        return [item for item in changes if isinstance(item, dict)]
    page = list_changes(source, mode="incremental")
    items = page.get("items")
    if not isinstance(items, list):
        return []
    return [
        {"external_id": item.get("external_id"), "acl": item.get("acl") or []}
        for item in items
        if isinstance(item, dict)
    ]


def check_access(source: dict[str, object], external_id: str, user_id: str) -> bool:
    """Late verification. Timeout and errors fail closed at the caller."""
    config = _config(source)
    denied = config.get("late_deny")
    if isinstance(denied, dict) and user_id in {str(item) for item in denied.get(external_id, [])}:
        return False
    allowed = config.get("late_allow")
    if isinstance(allowed, dict):
        people = {str(item) for item in allowed.get(external_id, [])}
        return user_id in people
    return True


def fetch_bytes(item: dict[str, object]) -> tuple[bytes, str]:
    if isinstance(item.get("text"), str):
        return str(item["text"]).encode(), str(item.get("mime_type") or "text/markdown")
    url = str(item.get("uri") or "")
    if url.startswith("http"):
        response = httpx.get(url, timeout=5.0, follow_redirects=False)
        response.raise_for_status()
        return response.content, str(item.get("mime_type") or "text/html")
    return b"", str(item.get("mime_type") or "text/plain")


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


def _web(config: dict[str, object]) -> dict[str, object]:
    start = str(config.get("url") or "")
    if not start:
        return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
    allow = (
        {str(item) for item in config.get("allowlist", [])}  # type: ignore[attr-defined]
        if isinstance(config.get("allowlist"), list)
        else set()
    )
    host = urlparse(start).netloc
    if allow and host not in allow:
        return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
    proxy = str(config.get("proxy") or "")
    client = httpx.Client(timeout=5.0, proxy=proxy or None, follow_redirects=False)
    try:
        robots = client.get(urljoin(start, "/robots.txt"))
        if robots.status_code == 200 and "Disallow: /" in robots.text:
            return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
        page = client.get(start, headers={"If-None-Match": str(config.get("etag") or "")})
    finally:
        client.close()
    if page.status_code == 304:
        return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
    digest = hashlib.sha256(page.content).hexdigest()
    return {
        "items": [
            {
                "external_id": start,
                "title": host or "Page",
                "uri": start,
                "mime_type": "text/html",
                "version_hint": page.headers.get("etag") or digest,
                "text": page.text,
                "acl": [],
            }
        ],
        "deleted_external_ids": [],
        "next_cursor": {"etag": page.headers.get("etag") or digest},
        "done": True,
    }


def _s3(config: dict[str, object]) -> dict[str, object]:
    listed = config.get("objects")
    if not isinstance(listed, list):
        listed = []
    items = []
    for row in listed:
        if not isinstance(row, dict):
            continue
        items.append(
            {
                "external_id": str(row.get("key") or row.get("external_id")),
                "title": str(row.get("key") or "object"),
                "uri": str(row.get("uri") or row.get("key") or ""),
                "mime_type": str(row.get("mime_type") or "text/plain"),
                "version_hint": str(row.get("etag") or ""),
                "text": str(row.get("text") or ""),
                "acl": row.get("acl") or [],
            }
        )
    deleted = config.get("deleted_keys")
    return {
        "items": items,
        "deleted_external_ids": list(deleted) if isinstance(deleted, list) else [],
        "next_cursor": {},
        "done": True,
    }


def _graph(config: dict[str, object], kind: str) -> dict[str, object]:
    url = str(config.get("url") or "")
    if not url:
        return {"items": [], "deleted_external_ids": [], "next_cursor": {}, "done": True}
    headers = {}
    token = str(config.get("token") or "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = httpx.get(url, headers=headers, timeout=5.0)
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
        items.append(_normalise(row, kind))
    return {"items": items, "deleted_external_ids": deleted, "next_cursor": {}, "done": True}


def _rows(config: dict[str, object]) -> dict[str, object]:
    rows = config.get("rows")
    chosen = rows if isinstance(rows, list) else []
    items = [_normalise(row, "database") for row in chosen if isinstance(row, dict)]
    return {"items": items, "deleted_external_ids": [], "next_cursor": {}, "done": True}


def _resources(config: dict[str, object]) -> dict[str, object]:
    rows = config.get("resources")
    chosen = rows if isinstance(rows, list) else []
    items = [_normalise(row, "mcp_resource") for row in chosen if isinstance(row, dict)]
    return {"items": items, "deleted_external_ids": [], "next_cursor": {}, "done": True}


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
