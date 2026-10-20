"""Repositories always carry a tenant context. Spec: docs/02-architecture/tenancy-isolation.md."""

from typing import TYPE_CHECKING

from ar_domain.db.context import TenantContext

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Base for tenant-scoped repositories.

    Construction without a :class:`TenantContext` is rejected by the type checker
    and at runtime.
    """

    def __init__(self, session: AsyncSession, ctx: TenantContext) -> None:
        if not isinstance(ctx, TenantContext):
            raise TypeError("repository requires a TenantContext")
        self.session = session
        self.ctx = ctx
