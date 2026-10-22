"""SharePoint via Microsoft Graph delta payloads."""

from ar_ingest.connectors.base import ConfigSource


class SharePointSource(ConfigSource):
    kind = "sharepoint"
