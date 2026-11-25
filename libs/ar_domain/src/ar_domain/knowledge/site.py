"""What a web knowledge source reads: one page, or a site walked from where it starts.

Spec: docs/03-specs/10-knowledge.md §5, docs/05-contracts/definition-schema.md §5.

A source names where to start (``start_urls``, or the single ``url``), the hosts it may
read (``allowed_domains``), how many pages at most (``max_pages``) and how far to follow
links from where it starts (``max_depth``). A start address that is a sitemap, a sitemap
index or a feed is opened and its entries are the pages; they are at depth 0. Each page
is one document, named by the page's own title and addressed by its own URL, so an answer
that cites it links to the page a person can open.

The site's robots.txt is always honoured. A page the site says has not changed is not
read again, and a listing that was read whole says which documents are gone.
"""

from __future__ import annotations

import hashlib
import html
import mimetypes
import re
import time
from typing import TYPE_CHECKING
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

_PAGES_DEFAULT = 200
_PAGES_MAX = 10_000
_DEPTH_MAX = 5
_HOPS = 3
_DELAY_MAX_S = 5.0
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_SPACE = re.compile(r"\s+")
# Addresses that are part of how a page looks or behaves, never a document to read.
_NOT_DOCUMENTS = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".avif",
        ".css", ".js", ".mjs", ".map", ".woff", ".woff2", ".ttf", ".eot", ".otf",
        ".mp3", ".mp4", ".mov", ".avi", ".webm", ".wav", ".zip", ".gz", ".tar", ".rar",
        ".7z", ".exe", ".dmg", ".iso",
    }
)  # fmt: skip


class NotModified(Exception):  # noqa: N818 - a result, not a failure
    """The site says the page is as it was when it was last read."""


def walk(source: dict[str, object], config: dict[str, object], *, mode: str) -> dict[str, object]:
    """The source's pages as items. A page is read when it is ingested, not listed."""
    from ar_common.egress_http import sync_client  # noqa: PLC0415
    from ar_domain.knowledge.fetchers import _hosts  # noqa: PLC0415

    config = _plain(config)
    starts = _many(config.get("start_urls")) or _many(config.get("url"))
    if not starts:
        return _page([], {}, complete=False)
    if str(config.get("proxy") or "").strip():
        return _page([], {}, complete=False, error="a proxy is configured and is refused")
    allowed = set(_many(config.get("allowed_domains")) or _many(config.get("allowlist")))
    allowed = allowed or {urlparse(url).hostname or "" for url in starts}
    one_page = "start_urls" not in config and "max_pages" not in config
    most = 1 if one_page else _bounded(config.get("max_pages"), _PAGES_DEFAULT, _PAGES_MAX)
    depth_limit = _bounded(config.get("max_depth"), 0, _DEPTH_MAX, least=0)
    cursor = source.get("cursor")
    known = cursor.get("pages") if isinstance(cursor, dict) else None
    before: dict[str, Any] = dict(known) if isinstance(known, dict) else {}
    after: dict[str, Any] = {}
    site = _Site(sync_client(allow=_hosts(source), timeout=15.0, follow_redirects=False), source)
    walked = _Walk(site, allowed, most, depth_limit, mode=mode, before=before, after=after)
    try:
        for url in starts:
            walked.start(url)
        walked.follow()
    finally:
        # The pages are read after this returns, one at a time as each is ingested, and
        # each read opens its own connection.
        site.client.close()
    if walked.refused and not walked.items:
        return _page([], {}, complete=False, error=walked.refused)
    return _page(walked.items, {"pages": after}, complete=walked.whole)


def _page(
    items: list[dict[str, object]], cursor: dict[str, object], *, complete: bool, error: str = ""
) -> dict[str, object]:
    page: dict[str, object] = {
        "items": items,
        "deleted_external_ids": [],
        "next_cursor": cursor,
        "done": True,
        "complete": complete,
    }
    if error:
        page["error"] = error
    return page


class _Site:
    """Reads addresses of the sites a source names, by each site's own rules."""

    def __init__(self, client: httpx.Client, source: dict[str, object]) -> None:
        self.client = client
        self.source = source
        self.rules: dict[str, Any] = {}
        self.last = 0.0

    def allowed(self, url: str) -> bool:
        from ar_common import robots  # noqa: PLC0415
        from ar_common.egress_http import user_agent  # noqa: PLC0415

        where = robots.address(url)
        if where not in self.rules:
            try:
                answer = self.client.get(where)
                text = robots.text_for(answer.status_code, answer.text)
            except httpx.HTTPError:
                text = robots.text_for(None, "")
            self.rules[where] = robots.Robots(text, user_agent())
        return bool(self.rules[where].allows(url))

    def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """One address, following a redirect only to a host the source may read."""
        from ar_common import robots  # noqa: PLC0415
        from ar_common.egress_http import guard  # noqa: PLC0415
        from ar_domain.knowledge.fetchers import _hosts  # noqa: PLC0415

        rules = self.rules.get(robots.address(url))
        wait = rules.delay_s() if rules is not None else None
        if wait:
            pause = min(float(wait), _DELAY_MAX_S) - (time.monotonic() - self.last)
            if pause > 0:
                time.sleep(pause)
        target = url
        for _ in range(_HOPS + 1):
            problem = guard(target, _hosts(self.source))
            if problem is not None:
                raise httpx.HTTPError(problem)
            response = self.client.get(target, headers=headers or {})
            self.last = time.monotonic()
            where = response.headers.get("location", "")
            if response.status_code not in {301, 302, 303, 307, 308} or not where:
                return response
            target = urljoin(target, where)
        raise httpx.HTTPError("the address redirects too many times")


class _Walk:
    """The pages found from where a source starts, up to its limits."""

    def __init__(
        self,
        site: _Site,
        allowed: set[str],
        most: int,
        depth_limit: int,
        *,
        mode: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        self.site = site
        self.allowed = allowed
        self.most = most
        self.depth_limit = depth_limit
        self.mode = mode
        self.before = before
        self.after = after
        self.items: list[dict[str, object]] = []
        self.seen: set[str] = set()
        self.queue: list[tuple[str, int, bytes | None, httpx.Response | None]] = []
        self.whole = True
        self.refused = ""

    def start(self, url: str) -> None:
        """Open one start address. A sitemap or feed gives its entries; a page is itself."""
        from ar_domain.tools.web import _from_xml  # noqa: PLC0415

        if not self._may(url):
            self.whole = False
            self.refused = self.refused or (
                "the site's robots.txt asks automated readers not to fetch this page"
                if self._in_scope(url)
                else "the start address is not on a host this source may read"
            )
            return
        if self.depth_limit == 0 and not _looks_listed(url):
            # A page that is only itself is read when it is ingested, like any other.
            self._add(url, 0, "", "")
            return
        try:
            response = self.site.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self.whole = False
            self.refused = self.refused or f"the start address could not be read ({exc})"
            return
        listed = _from_xml(response, url)
        if listed is None:
            self._add(url, 0, "", "", response=response)
            return
        for entry in listed["items"]:
            address = str(entry.get("url") or "")
            if _looks_listed(address) and address not in self.seen:
                # A sitemap index names more sitemaps. They are opened the same way.
                self.seen.add(address)
                self.start(address)
            else:
                self._add(address, 0, str(entry.get("title") or ""), str(entry.get("date") or ""))

    def follow(self) -> None:
        """Read the pages that links are followed from, level by level."""
        from ar_domain.tools.web import _from_page  # noqa: PLC0415

        at = 0
        while at < len(self.queue):
            url, depth, _body, response = self.queue[at]
            at += 1
            if depth >= self.depth_limit:
                continue
            if response is None:
                try:
                    response = self.site.get(url)
                    response.raise_for_status()
                except httpx.HTTPError:
                    # Its links are not known, so the listing is not the whole site.
                    self.whole = False
                    continue
                self.queue[at - 1] = (url, depth, None, response)
                self._hold(url, response)
            if "html" not in response.headers.get("content-type", "text/html").lower():
                continue
            for link in _from_page(response.text, url, sorted(self.allowed))["items"]:
                self._add(str(link["url"]), depth + 1, str(link.get("title") or ""), "")

    def _in_scope(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and (
            (parsed.hostname or "") in self.allowed or parsed.netloc in self.allowed
        )

    def _may(self, url: str) -> bool:
        return self._in_scope(url) and self.site.allowed(url)

    def _add(
        self,
        address: str,
        depth: int,
        title: str,
        changed: str,
        *,
        response: httpx.Response | None = None,
    ) -> None:
        url = urldefrag(address).url
        if not url or url in self.seen:
            return
        suffix = "." + urlparse(url).path.rsplit(".", 1)[-1].lower() if "." in url else ""
        if suffix in _NOT_DOCUMENTS or not self._may(url):
            return
        if len(self.items) >= self.most:
            self.whole = False
            return
        self.seen.add(url)
        item: dict[str, object] = {
            "external_id": url,
            "title": title or _name(url),
            "uri": url,
            "mime_type": "",
            "version_hint": changed,
            "acl": [],
        }
        item["load"] = self._reader(item, changed)
        self.items.append(item)
        self.queue.append((url, depth, None, response))
        if response is not None:
            self._hold(url, response)

    def _hold(self, url: str, response: httpx.Response) -> None:
        """Keep what was read to find links, so the page is not asked for twice."""
        for item in self.items:
            if item["external_id"] == url:
                item["held"] = response
                return

    def _read(self, url: str, headers: dict[str, str]) -> httpx.Response:
        """One page, on a connection of its own: the walk's is closed by the time it is read."""
        from ar_common.egress_http import sync_client  # noqa: PLC0415
        from ar_domain.knowledge.fetchers import _hosts  # noqa: PLC0415

        client = sync_client(allow=_hosts(self.site.source), timeout=15.0, follow_redirects=False)
        reader = _Site(client, self.site.source)
        reader.rules = self.site.rules
        try:
            return reader.get(url, headers)
        finally:
            client.close()

    def _reader(self, item: dict[str, object], changed: str) -> Callable[[], tuple[bytes, str]]:
        url = str(item["external_id"])
        earlier = self.before.get(url)
        last: dict[str, Any] = dict(earlier) if isinstance(earlier, dict) else {}

        def read() -> tuple[bytes, str]:
            held = item.pop("held", None)
            conditional = self.mode != "full" and item.get("known") is True and held is None
            if conditional and changed and last.get("changed") == changed:
                # The sitemap gives the same date as last time: the page is not asked for.
                self.after[url] = last
                raise NotModified
            headers: dict[str, str] = {}
            if conditional and last.get("etag"):
                headers["If-None-Match"] = str(last["etag"])
            elif conditional and last.get("lastModified"):
                headers["If-Modified-Since"] = str(last["lastModified"])
            response = held if isinstance(held, httpx.Response) else self._read(url, headers)
            if response.status_code == 304:
                self.after[url] = last
                raise NotModified
            response.raise_for_status()
            mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            mime = mime or mimetypes.guess_type(urlparse(url).path)[0] or "text/html"
            if "html" in mime:
                found = _TITLE.search(response.text)
                named = _SPACE.sub(" ", html.unescape(found.group(1))).strip() if found else ""
                if named:
                    item["title"] = named[:300]
            measured = {
                "status": response.status_code,
                "etag": response.headers.get("etag", ""),
                "lastModified": response.headers.get("last-modified", ""),
            }
            item["measured"] = measured
            item["version_hint"] = (
                changed or measured["etag"] or hashlib.sha256(response.content).hexdigest()
            )
            self.after[url] = {
                "etag": measured["etag"],
                "lastModified": measured["lastModified"],
                "changed": changed,
            }
            return response.content, mime

        return read


_NAMES = {
    "startUrls": "start_urls",
    "allowedDomains": "allowed_domains",
    "maxPages": "max_pages",
    "maxDepth": "max_depth",
}


def _plain(config: dict[str, object]) -> dict[str, object]:
    """The settings under one spelling: a definition file and the API may each use either."""
    return {_NAMES.get(key, key): value for key, value in config.items()}


def _looks_listed(url: str) -> bool:
    """Whether an address is, by its name, a list of pages and not a page."""
    path = urlparse(url).path.lower()
    return path.endswith((".xml", ".xml.gz", ".rss", ".atom")) or path.rstrip("/").endswith(
        ("/feed", "/rss")
    )


def _name(url: str) -> str:
    parsed = urlparse(url)
    last = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return last or parsed.hostname or "Page"


def _many(value: object) -> list[str]:
    """A setting that names several things: a list, or one string with spaces or commas."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part for part in re.split(r"[\s,]+", value.strip()) if part]
    return []


def _bounded(value: object, default: int, most: int, *, least: int = 1) -> int:
    try:
        number = int(str(value).strip()) if value is not None and str(value).strip() else default
    except ValueError:
        number = default
    return max(least, min(number, most))
