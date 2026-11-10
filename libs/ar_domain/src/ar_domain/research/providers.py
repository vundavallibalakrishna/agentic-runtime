"""Pluggable search providers. API keys come from named secrets.

Hosts below are the providers' public API addresses. A deployment overrides
``base_url``. Nothing here is a credential.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from ar_domain.tools.http_tools import fetch_text
from ar_domain.tools.named_secrets import read_named_secret

if TYPE_CHECKING:
    from typing import Any

PROVIDERS = ("fixture", "searxng", "brave", "tavily", "bing")

_DEFAULT_HOSTS = {
    "brave": "https://api.search.brave.com/res/v1/web/search",
    "tavily": "https://api.tavily.com/search",
    "bing": "https://api.bing.microsoft.com/v7.0/search",
}


def provider_config(store: Any, tenant_id: object) -> dict[str, str]:
    """Which provider is on, and the secret name. The secret value stays out."""
    from ar_domain.identity.tenant_settings import settings_for  # noqa: PLC0415

    settings = settings_for(store, tenant_id)
    raw = settings.get("search")
    if not isinstance(raw, dict):
        return {"provider": "fixture", "secret_name": "", "base_url": ""}
    name = str(raw.get("provider") or "fixture").strip().lower()
    if name not in PROVIDERS:
        name = "fixture"
    return {
        "provider": name,
        "secret_name": str(raw.get("secret_name") or raw.get("secretName") or ""),
        "base_url": str(raw.get("base_url") or raw.get("baseUrl") or "").rstrip("/"),
    }


def search(  # noqa: PLR0911
    store: Any, tenant_id: object, query: str, *, limit: int = 4
) -> list[dict[str, str]]:
    """One search. Fixture results need no network and no key."""
    config = provider_config(store, tenant_id)
    name = config["provider"]
    if name == "fixture" or (name != "searxng" and not config["secret_name"]):
        return fixture_hits(query, limit=limit)
    token = ""
    if config["secret_name"]:
        token = read_named_secret(store, tenant_id, config["secret_name"]) or ""
        if not token and name != "searxng":
            return fixture_hits(query, limit=limit)
    try:
        if name == "searxng":
            return _searxng(store, config["base_url"], query, limit)
        if name == "brave":
            return _brave(store, config["base_url"], token, query, limit)
        if name == "tavily":
            return _tavily(store, config["base_url"], token, query, limit)
        if name == "bing":
            return _bing(store, config["base_url"], token, query, limit)
    except Exception:  # noqa: BLE001 - a provider failure is an empty result, not a crash
        return []
    return fixture_hits(query, limit=limit)


def fixture_hits(query: str, *, limit: int = 4) -> list[dict[str, str]]:
    """Two stable pages. The text is generic and contains the query."""
    topic = " ".join(query.split())[:180] or "the question"
    rows = [
        {
            "url": "fixture://notes/overview",
            "title": "Overview",
            "snippet": f"Overview: {topic} is described in the stored notes.",
        },
        {
            "url": "fixture://notes/detail",
            "title": "Detail",
            "snippet": f"Detail: a second source agrees that {topic} can be checked.",
        },
    ]
    return rows[: max(1, limit)]


def fixture_page(url: str, query: str = "") -> str | None:
    """Full text for a fixture URL, or None when the URL is not a fixture."""
    if not url.startswith("fixture://"):
        return None
    topic = query or "the question"
    if url.endswith("/detail"):
        return (
            f"Detail: a second source agrees that {topic} can be checked. "
            "The stored sentence is the only claim this page supports."
        )
    return (
        f"Overview: {topic} is described in the stored notes. "
        "Readers can quote this sentence because it is on the page."
    )


def _searxng(store: Any, base: str, query: str, limit: int) -> list[dict[str, str]]:
    if not base:
        return []
    url = f"{base}/search?{urlencode({'q': query, 'format': 'json'})}"
    status, text = fetch_text(store, "GET", url, timeout=20)
    if status >= 300:
        return []
    return _hits_from_json(text, limit, title_key="title", url_key="url", snippet_key="content")


def _brave(store: Any, base: str, token: str, query: str, limit: int) -> list[dict[str, str]]:
    url = base or _DEFAULT_HOSTS["brave"]
    status, text = fetch_text(
        store,
        "GET",
        f"{url}?{urlencode({'q': query, 'count': str(limit)})}",
        headers={"Accept": "application/json", "X-Subscription-Token": token},
        timeout=20,
    )
    if status >= 300:
        return []
    import orjson  # noqa: PLC0415

    try:
        payload = orjson.loads(text)
    except orjson.JSONDecodeError:
        return []
    web = payload.get("web") if isinstance(payload, dict) else None
    results = web.get("results") if isinstance(web, dict) else None
    return _rows(results, limit)


def _tavily(store: Any, base: str, token: str, query: str, limit: int) -> list[dict[str, str]]:
    url = base or _DEFAULT_HOSTS["tavily"]
    status, text = fetch_text(
        store,
        "POST",
        url,
        headers={"Authorization": f"Bearer {token}"},
        json_body={"query": query, "max_results": limit, "api_key": token},
        timeout=20,
    )
    if status >= 300:
        return []
    return _hits_from_json(text, limit, title_key="title", url_key="url", snippet_key="content")


def _bing(store: Any, base: str, token: str, query: str, limit: int) -> list[dict[str, str]]:
    url = base or _DEFAULT_HOSTS["bing"]
    status, text = fetch_text(
        store,
        "GET",
        f"{url}?{urlencode({'q': query, 'count': str(limit)})}",
        headers={"Ocp-Apim-Subscription-Key": token},
        timeout=20,
    )
    if status >= 300:
        return []
    import orjson  # noqa: PLC0415

    try:
        payload = orjson.loads(text)
    except orjson.JSONDecodeError:
        return []
    web = payload.get("webPages") if isinstance(payload, dict) else None
    values = web.get("value") if isinstance(web, dict) else None
    rows: list[dict[str, str]] = []
    if not isinstance(values, list):
        return rows
    for item in values[:limit]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "url": str(item.get("url") or ""),
                "title": str(item.get("name") or ""),
                "snippet": str(item.get("snippet") or ""),
            }
        )
    return [row for row in rows if row["url"]]


def _hits_from_json(
    text: str, limit: int, *, title_key: str, url_key: str, snippet_key: str
) -> list[dict[str, str]]:
    import orjson  # noqa: PLC0415

    try:
        payload = orjson.loads(text)
    except orjson.JSONDecodeError:
        return []
    results = payload.get("results") if isinstance(payload, dict) else None
    return _named(results, limit, title_key, url_key, snippet_key)


def _named(
    results: object, limit: int, title_key: str, url_key: str, snippet_key: str
) -> list[dict[str, str]]:
    if not isinstance(results, list):
        return []
    rows: list[dict[str, str]] = []
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        url = str(item.get(url_key) or "")
        if not url:
            continue
        rows.append(
            {
                "url": url,
                "title": str(item.get(title_key) or url),
                "snippet": str(item.get(snippet_key) or ""),
            }
        )
    return rows


def _rows(results: object, limit: int) -> list[dict[str, str]]:
    return _named(results, limit, "title", "url", "description")
