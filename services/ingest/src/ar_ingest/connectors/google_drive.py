"""Google Drive changes."""

from ar_ingest.connectors.base import ConfigSource


class GoogleDriveSource(ConfigSource):
    kind = "google_drive"
