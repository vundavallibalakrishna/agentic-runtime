"""Read-only table rows supplied by a guarded query."""

from ar_ingest.connectors.base import ConfigSource


class DatabaseSource(ConfigSource):
    kind = "database"
