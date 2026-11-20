"""Secrets kept in memory, for a test application that has no database.

Test setup plugs ``provider`` into ``app.state.secret_provider``. It answers the same
calls as ``ar_domain.secrets.book.SecretBook``. A value is also written to the store's
named book, which is where a tool that takes a secret name looks in a process with no
database behind it.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError, NotFoundError
from ar_domain.secrets.service import SecretMetadata
from ar_domain.tools.named_secrets import write_named_secret

if TYPE_CHECKING:
    from collections.abc import Callable

    from ar_domain.db.context import TenantContext


class MemorySecrets:
    """One tenant's view of the secrets held on ``held``."""

    def __init__(
        self,
        store: Any,
        held: dict[uuid.UUID, tuple[uuid.UUID, SecretMetadata]],
        ctx: TenantContext,
    ) -> None:
        self.store = store
        self.held = held
        self.ctx = ctx

    async def list(self) -> list[SecretMetadata]:
        return [row for tenant, row in self.held.values() if tenant == self.ctx.tenant_id]

    async def create(self, name: str, kind: str, value: str, description: str) -> SecretMetadata:
        if any(row.name == name for row in await self.list()):
            raise ConflictError("a secret with that name already exists")
        row = SecretMetadata(uuid.uuid4(), name, kind, 1, description, None)
        self.held[row.id] = (self.ctx.tenant_id, row)
        write_named_secret(self.store, self.ctx.tenant_id, name, value)
        return row

    async def get(self, secret_id: uuid.UUID) -> SecretMetadata:
        found = self.held.get(secret_id)
        if found is None or found[0] != self.ctx.tenant_id:
            raise NotFoundError("secret not found")
        return found[1]

    async def describe(self, secret_id: uuid.UUID, description: str) -> SecretMetadata:
        row = await self.get(secret_id)
        updated = SecretMetadata(row.id, row.name, row.kind, row.version, description, None)
        self.held[secret_id] = (self.ctx.tenant_id, updated)
        return updated

    async def rotate(self, secret_id: uuid.UUID, value: str) -> SecretMetadata:
        row = await self.get(secret_id)
        updated = SecretMetadata(row.id, row.name, row.kind, row.version + 1, row.description, None)
        self.held[secret_id] = (self.ctx.tenant_id, updated)
        write_named_secret(self.store, self.ctx.tenant_id, row.name, value)
        return updated

    async def delete(self, secret_id: uuid.UUID) -> None:
        row = await self.get(secret_id)
        self.held.pop(secret_id, None)
        book = getattr(self.store, "named_secrets", None)
        if isinstance(book, dict):
            for key, kept in list(book.items()):
                if (
                    isinstance(kept, dict)
                    and str(kept.get("tenant_id")) == str(self.ctx.tenant_id)
                    and kept.get("name") == row.name
                ):
                    book.pop(key, None)


def provider(store: Any) -> Callable[[TenantContext], MemorySecrets]:
    """What test setup assigns to ``app.state.secret_provider``."""
    held: dict[uuid.UUID, tuple[uuid.UUID, SecretMetadata]] = {}
    return lambda ctx: MemorySecrets(store, held, ctx)
