"""ar-connector-sdk. Spec: docs/05-contracts/connector-sdk.md."""

from ar_connector_sdk.conformance import conformance_errors
from ar_connector_sdk.context import ContextError, ToolContext, annotations
from ar_connector_sdk.knowledge import DocumentSource
from ar_connector_sdk.server import ToolServer

__version__ = "0.1.0"

__all__ = [
    "ContextError",
    "DocumentSource",
    "ToolContext",
    "ToolServer",
    "annotations",
    "conformance_errors",
]
