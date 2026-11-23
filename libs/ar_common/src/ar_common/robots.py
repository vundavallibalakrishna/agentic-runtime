"""Read a site's robots.txt and say whether this install may fetch an address.

The rules are RFC 9309's. A site with no robots.txt (a 4xx answer) allows everything. A
site whose robots.txt cannot be read (a 5xx answer, or no answer) allows nothing until it
can be. Nothing here fetches: the caller hands over what the site answered.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

_MAX_CHARS = 512_000
ALLOW_ALL = ""
DENY_ALL = "User-agent: *\nDisallow: /\n"


@dataclass(frozen=True, slots=True)
class Robots:
    """One site's rules, as they apply to one User-Agent."""

    text: str
    agent: str

    def allows(self, url: str) -> bool:
        """Whether ``url`` may be fetched."""
        return _parsed(self.text).can_fetch(_token(self.agent), url)

    def delay_s(self) -> float | None:
        """The pause the site asks for between requests, when it asks for one."""
        found = _parsed(self.text).crawl_delay(_token(self.agent))
        return float(found) if found is not None else None

    def sitemaps(self) -> list[str]:
        """The sitemap addresses the file names."""
        return list(_parsed(self.text).site_maps() or [])


def text_for(status: int | None, body: str) -> str:
    """The rules to keep for what the site answered to a request for robots.txt.

    ``status`` is None when the site gave no answer at all.
    """
    if status is None or status >= 500:
        return DENY_ALL
    if status >= 400:
        return ALLOW_ALL
    return body[:_MAX_CHARS]


def address(url: str) -> str:
    """Where the robots.txt for ``url`` lives."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def _parsed(text: str) -> RobotFileParser:
    parser = RobotFileParser()
    parser.parse(text.splitlines())
    return parser


def _token(agent: str) -> str:
    """The product name a robots.txt group is matched on: the part before any version."""
    first = agent.strip().split(" ", 1)[0]
    return first.split("/", 1)[0] or "*"
