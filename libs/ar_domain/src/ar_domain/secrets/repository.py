"""Secret metadata queries."""

import uuid  # noqa: TC003

from sqlalchemy import select

from ar_domain.db import BaseRepository
from ar_domain.secrets.models import SecretRef


class SecretRepository(BaseRepository):
    """Tenant-scoped secret metadata. Values stay in the secret store."""

    async def list_refs(self) -> list[SecretRef]:
        rows = await self.session.scalars(
            select(SecretRef)
            .where(SecretRef.tenant_id == self.ctx.tenant_id)
            .order_by(SecretRef.name)
        )
        return list(rows.all())

    async def get(self, secret_id: uuid.UUID) -> SecretRef | None:
        return await self.session.scalar(
            select(SecretRef).where(
                SecretRef.tenant_id == self.ctx.tenant_id, SecretRef.id == secret_id
            )
        )
