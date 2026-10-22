"""Confluence pages and restrictions."""

from ar_ingest.connectors.base import ConfigSource


class ConfluenceSource(ConfigSource):
    kind = "confluence"
