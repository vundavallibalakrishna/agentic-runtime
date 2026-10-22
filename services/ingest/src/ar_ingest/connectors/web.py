"""Web crawl. robots.txt, ETag and the allowlist are applied in the fetcher."""

from ar_ingest.connectors.base import ConfigSource


class WebSource(ConfigSource):
    kind = "web"
