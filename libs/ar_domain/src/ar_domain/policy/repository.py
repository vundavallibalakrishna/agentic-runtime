"""SQL access for policies. The dev API uses PolicyBook (OQ-31)."""

from ar_domain.db import BaseRepository


class PolicyRepository(BaseRepository):
    """Tenant-scoped policy rows. Services do not import this module."""
