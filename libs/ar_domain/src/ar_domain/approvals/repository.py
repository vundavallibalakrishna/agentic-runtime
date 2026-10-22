"""SQL access for approvals. The dev API uses ApprovalBook (OQ-31)."""

from ar_domain.db import BaseRepository


class ApprovalRepository(BaseRepository):
    """Tenant-scoped approval rows. Services do not import this module."""
