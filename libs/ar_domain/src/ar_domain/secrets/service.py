"""Secret metadata service. Spec: docs/03-specs/03-secrets-credentials.md."""

import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ar_common.errors import NotFoundError
from ar_common.time import utcnow
from ar_domain.secrets.models import SecretRef

if TYPE_CHECKING:
    from ar_domain.db.context import TenantContext
    from ar_domain.secrets.store import SecretStore


@dataclass(frozen=True, slots=True)
class SecretMetadata:
    """API view of a secret. The value is never included."""

    id: uuid.UUID
    name: str
    kind: str
    version: int
    description: str
    owner_user_id: uuid.UUID | None


class SecretService:
    """Create, resolve and rotate secrets through a :class:`SecretStore`."""

    def __init__(self, store: SecretStore, *, cache_ttl_s: int) -> None:
        self.store = store
        self.cache_ttl_s = cache_ttl_s
        self._cache: dict[uuid.UUID, tuple[float, bytes]] = {}

    async def create(
        self,
        ctx: TenantContext,
        *,
        name: str,
        kind: str,
        value: bytes,
        description: str = "",
        owner_user_id: uuid.UUID | None = None,
        backend: str,
    ) -> SecretRef:
        """Store the value and return an unsaved ``SecretRef`` for the caller to insert."""
        secret_id = uuid.uuid4()
        path = _path(ctx.tenant_id, secret_id)
        await self.store.put(path, value, aad=_aad(ctx.tenant_id, secret_id))
        return SecretRef(
            id=secret_id,
            tenant_id=ctx.tenant_id,
            name=name,
            kind=kind,
            backend=backend,
            path=path,
            version=1,
            description=description,
            owner_user_id=owner_user_id,
            created_by=ctx.user_id,
        )

    async def resolve(self, ctx: TenantContext, ref: SecretRef) -> bytes:
        """Return plaintext, using the in-process cache when it is fresh."""
        cached = self._cache.get(ref.id)
        now = time.monotonic()
        if cached is not None and now - cached[0] < self.cache_ttl_s:
            return cached[1]
        value = await self.store.get(ref.path, aad=_aad(ctx.tenant_id, ref.id))
        self._cache[ref.id] = (now, value)
        return value

    async def rotate(self, ctx: TenantContext, ref: SecretRef, value: bytes) -> SecretMetadata:
        await self.store.put(ref.path, value, aad=_aad(ctx.tenant_id, ref.id))
        ref.version += 1
        ref.rotated_at = utcnow()
        self._cache.pop(ref.id, None)
        return _meta(ref)

    async def delete(self, ctx: TenantContext, ref: SecretRef) -> None:
        del ctx
        await self.store.delete(ref.path)
        self._cache.pop(ref.id, None)

    def metadata(self, ref: SecretRef) -> SecretMetadata:
        return _meta(ref)

    def visible(self, ctx: TenantContext, ref: SecretRef) -> bool:
        """Personal secrets are visible to the owner and to secret managers."""
        if ref.owner_user_id is None:
            return True
        if ctx.user_id == ref.owner_user_id:
            return True
        return ctx.principal.allows("secrets:manage")


def require_ref(ref: SecretRef | None) -> SecretRef:
    if ref is None:
        raise NotFoundError("secret not found")
    return ref


def _path(tenant_id: uuid.UUID, secret_id: uuid.UUID) -> str:
    return f"tenants/{tenant_id}/secrets/{secret_id}"


def _aad(tenant_id: uuid.UUID, secret_id: uuid.UUID) -> bytes:
    return f"{tenant_id}:{secret_id}".encode()


def _meta(ref: SecretRef) -> SecretMetadata:
    return SecretMetadata(
        id=ref.id,
        name=ref.name,
        kind=ref.kind,
        version=ref.version,
        description=ref.description,
        owner_user_id=ref.owner_user_id,
    )
