"""MCP resources listed through the gateway."""

from ar_ingest.connectors.base import ConfigSource


class McpResourceSource(ConfigSource):
    kind = "mcp_resource"
