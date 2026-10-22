"""Built-in knowledge connectors."""

from ar_ingest.connectors.base import ConfigSource
from ar_ingest.connectors.confluence import ConfluenceSource
from ar_ingest.connectors.database import DatabaseSource
from ar_ingest.connectors.google_drive import GoogleDriveSource
from ar_ingest.connectors.mcp_resource import McpResourceSource
from ar_ingest.connectors.s3 import S3Source
from ar_ingest.connectors.sharepoint import SharePointSource
from ar_ingest.connectors.upload import UploadSource
from ar_ingest.connectors.web import WebSource

__all__ = [
    "ConfigSource",
    "ConfluenceSource",
    "DatabaseSource",
    "GoogleDriveSource",
    "McpResourceSource",
    "S3Source",
    "SharePointSource",
    "UploadSource",
    "WebSource",
]
