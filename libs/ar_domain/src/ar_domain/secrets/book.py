"""One tenant's named secrets: the rows, the values and the audit trail.

The value goes to the install's ``SecretStore`` and is never returned. Every change is
audited in the transaction that makes it. Spec: docs/03-specs/03-secrets-credentials.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.settings import get_settings
from ar_domain.audit.actions import AuditAction
from ar_domain.audit.service import record_for_context
from ar_domain.secrets.cached import secret_backend
from ar_domain.secrets.repository import SecretRepository
from ar_domain.secrets.service import SecretMetadata, SecretService

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from ar_domain.db.context import TenantContext
    from ar_domain.secrets.models import SecretRef

KINDS = frozenset(
    {
        "api_key",
        "basic_auth",
        "bearer_token",
        "oauth_client",
        "oauth_refresh_token",
        "db_dsn",
        "webhook_secret",
        "generic",
    }
)


MAX_VALUE_BYTES = 64 * 1024


def _sized(value: str) -> None:
    if not value:
        raise ValidationFailedError("a secret needs a value")
    if len(value.encode()) > MAX_VALUE_BYTES:
        raise ValidationFailedError("a secret value may be at most 64 KiB")


class SecretBook:
    """The secrets of the tenant in ``ctx``, inside the caller's transaction."""

    def __init__(self, session: AsyncSession, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx
        self.rows = SecretRepository(session, ctx)

    async def list(self) -> list[SecretMetadata]:
        service = self._service(get_settings().secrets_backend)
        refs = await self.rows.list_refs()
        # A personal secret (it has an owner) is never listed.
        return [service.metadata(ref) for ref in refs if ref.owner_user_id is None]

    async def create(self, name: str, kind: str, value: str, description: str) -> SecretMetadata:
        wanted = name.strip()
        if not wanted:
            raise ValidationFailedError("a secret needs a name")
        if kind not in KINDS:
            raise ValidationFailedError(f"kind must be one of: {', '.join(sorted(KINDS))}")
        _sized(value)
        backend = get_settings().secrets_backend
        service = self._service(backend)
        ref = await service.create(
            self.ctx,
            name=wanted,
            kind=kind,
            value=value.encode(),
            description=description,
            backend=backend,
        )
        self.session.add(ref)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ConflictError("a secret with that name already exists") from exc
        await self._audit(AuditAction.SECRET_CREATED, ref)
        return service.metadata(ref)

    async def get(self, secret_id: uuid.UUID) -> SecretMetadata:
        ref = await self._ref(secret_id)
        return self._service(ref.backend).metadata(ref)

    async def describe(self, secret_id: uuid.UUID, description: str) -> SecretMetadata:
        ref = await self._ref(secret_id)
        ref.description = description
        await self.session.flush()
        await self._audit(AuditAction.SECRET_UPDATED, ref)
        return self._service(ref.backend).metadata(ref)

    async def rotate(self, secret_id: uuid.UUID, value: str) -> SecretMetadata:
        ref = await self._ref(secret_id)
        _sized(value)
        meta = await self._service(ref.backend).rotate(self.ctx, ref, value.encode())
        await self.session.flush()
        await self._audit(AuditAction.SECRET_ROTATED, ref)
        return meta

    async def delete(self, secret_id: uuid.UUID) -> None:
        ref = await self._ref(secret_id)
        await self._service(ref.backend).delete(self.ctx, ref)
        await self.session.delete(ref)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ConflictError("the secret is still in use and cannot be deleted") from exc
        await self._audit(AuditAction.SECRET_DELETED, ref)

    async def _ref(self, secret_id: uuid.UUID) -> SecretRef:
        ref = await self.rows.get(secret_id)
        if ref is None or not self._service(ref.backend).visible(self.ctx, ref):
            raise NotFoundError("secret not found")
        return ref

    def _service(self, backend: str) -> SecretService:
        # No cache: the service lives for one request and never reads a value here.
        return SecretService(
            secret_backend(self.session, self.ctx.tenant_id, backend), cache_ttl_s=0
        )

    async def _audit(self, action: AuditAction, ref: SecretRef) -> None:
        # The name and the kind, never the value.
        await record_for_context(
            self.session,
            self.ctx,
            action=action,
            target_type="secret",
            target_id=str(ref.id),
            detail={"name": ref.name, "kind": ref.kind, "version": ref.version},
        )
