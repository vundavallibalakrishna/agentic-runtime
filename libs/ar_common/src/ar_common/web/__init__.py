"""HTTP service template."""

from ar_common.web.app import create_app
from ar_common.web.health import ReadinessCheck

__all__ = ["ReadinessCheck", "create_app"]
