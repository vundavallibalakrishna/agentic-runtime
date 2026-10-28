"""Drop remote images and suspicious links. Spec: docs/06-security/prompt-injection.md §6."""

import re
from urllib.parse import urlparse

_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_B64 = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")


def filter_markdown(text: str, *, allow_hosts: tuple[str, ...] = ()) -> str:
    """Render-safe markdown. Remote images become their alt text."""

    def image(match: re.Match[str]) -> str:
        alt, url = match.group(1), match.group(2)
        host = urlparse(url).hostname or ""
        if host and host not in allow_hosts and not url.startswith("/"):
            return alt or "[image removed]"
        return match.group(0)

    def link(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        query = urlparse(url).query
        if len(query) > 200 or _B64.search(query):
            return f"{label} (link hidden)"
        return match.group(0)

    without_images = _IMAGE.sub(image, text)
    return _LINK.sub(link, without_images)


def link_rel() -> str:
    return "noopener noreferrer nofollow"
