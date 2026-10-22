"""Upload sources are filled by the documents API."""

from ar_ingest.connectors.base import ConfigSource


class UploadSource(ConfigSource):
    kind = "upload"
