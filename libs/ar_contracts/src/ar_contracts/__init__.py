"""Cross-process contracts. Spec: docs/02-architecture/service-decomposition.md §2."""

from ar_contracts.api_model import ApiModel
from ar_contracts.definitions import SCHEMA_MODELS
from ar_contracts.stream import RunEvent

__all__ = ["SCHEMA_MODELS", "ApiModel", "RunEvent", "__version__"]
__version__ = "0.1.0"
