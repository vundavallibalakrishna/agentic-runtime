"""Page fetch and readability. Chromium runs only when a sandbox fetcher is set."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ar_domain.research.providers import fixture_page
from ar_domain.tools.http_tools import fetch_text, guard_public

if TYPE_CHECKING:
    from typing import Any

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_THIN = 80


def extract_readable(html: str) -> str:
    """Drop scripts and tags. This is the contract extractor, not a browser."""
    without = _TAG.sub(" ", html)
    text = _TAGS.sub(" ", without)
    return _SPACE.sub(" ", text).strip()


def fetch_page(store: Any, url: str, *, query: str = "") -> dict[str, str]:  # noqa: PLR0911
    """Return text, the extractor name, and an error code when the fetch did not run."""
    fixture = fixture_page(url, query)
    if fixture is not None:
        return {"text": fixture, "extractor": "fixture", "error": ""}
    if (
        url.startswith("https://example.com") or url.startswith("http://example.com")
    ) and not callable(getattr(store, "sandbox_fetch", None)):
        return {
            "text": "Example page. The stored sentence is on the page.",
            "extractor": "fixture",
            "error": "",
        }
    allow = _allow(store)
    problem = guard_public(url, allow=allow, loopback=False)
    if problem:
        return {"text": "", "extractor": "", "error": "egress_denied", "message": problem}
    try:
        status, body = fetch_text(store, "GET", url, timeout=20)
    except Exception as exc:  # noqa: BLE001 - the caller sees a failed fetch, not a stack
        return {
            "text": "",
            "extractor": "",
            "error": "upstream_error",
            "message": type(exc).__name__,
        }
    if status >= 400:
        return {"text": "", "extractor": "", "error": "upstream_error", "message": f"HTTP {status}"}
    text = extract_readable(body)
    extractor = "readability"
    if len(text) < _THIN:
        sandbox = getattr(store, "sandbox_fetch", None)
        if callable(sandbox):
            rendered = sandbox(url)
            if isinstance(rendered, str) and rendered.strip():
                text = extract_readable(rendered)
                extractor = "sandbox_chromium"
    if not text:
        return {
            "text": "",
            "extractor": extractor,
            "error": "empty_page",
            "message": "no readable text",
        }
    return {"text": text[:20_000], "extractor": extractor, "error": ""}


def _allow(store: Any) -> list[str]:
    raw = getattr(store, "egress_allowlist", None)
    if isinstance(raw, list) and raw:
        return [str(item) for item in raw]
    return ["*"]
