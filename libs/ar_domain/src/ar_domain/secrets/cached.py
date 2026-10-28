"""Persist channel credentials through SecretStore in the catalogue transaction."""

from typing import TYPE_CHECKING

from ar_common.settings import get_settings
from ar_domain.secrets.crypto import parse_keyring
from ar_domain.secrets.models import SecretRef
from ar_domain.secrets.stores.db_encrypted import DbEncryptedStore
from ar_domain.secrets.stores.vault import VaultSecretStore

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from ar_domain.secrets.store import SecretStore


def _backend(session: AsyncSession, tenant_id: uuid.UUID, kind: str) -> SecretStore:
    settings = get_settings()
    if kind == "db_encrypted":
        return DbEncryptedStore(
            session,
            tenant_id=tenant_id,
            keyring=parse_keyring(settings.db_encryption_keys.get_secret_value()),
            active_key_id=settings.db_encryption_active_key,
        )
    if kind == "vault":
        import hvac  # noqa: PLC0415

        client = hvac.Client(url=settings.vault_addr, token=settings.vault_token.get_secret_value())
        return VaultSecretStore(client.secrets.kv.v2, mount=settings.vault_kv_mount)
    raise ValueError("Unsupported secret backend")


async def save_cached_secret(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    secret_id: uuid.UUID,
    value: bytes,
    user_id: uuid.UUID | None,
) -> None:
    """Save one immutable credential revision; existing revisions are not rewritten."""
    existing = await session.get(SecretRef, secret_id)
    if existing is not None:
        if existing.tenant_id != tenant_id:
            raise ValueError("Secret tenant mismatch")
        return
    settings = get_settings()
    path = f"tenants/{tenant_id}/secrets/{secret_id}"
    backend = _backend(session, tenant_id, settings.secrets_backend)
    await backend.put(path, value, aad=f"{tenant_id}:{secret_id}".encode())
    session.add(
        SecretRef(
            id=secret_id,
            tenant_id=tenant_id,
            name=f"channel-{secret_id}",
            kind="generic",
            backend=settings.secrets_backend,
            path=path,
            version=1,
            description="Channel integration credentials",
            created_by=user_id,
        )
    )
    await session.flush()


async def load_cached_secret(
    session: AsyncSession, tenant_id: uuid.UUID, secret_id: uuid.UUID
) -> bytes | None:
    """Resolve only a secret owned by the integration's tenant."""
    ref = await session.get(SecretRef, secret_id)
    if ref is None or ref.tenant_id != tenant_id:
        return None
    return await _backend(session, tenant_id, ref.backend).get(
        ref.path, aad=f"{tenant_id}:{secret_id}".encode()
    )
