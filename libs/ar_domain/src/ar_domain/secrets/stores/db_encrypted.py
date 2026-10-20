"""Database envelope backend. Spec: docs/03-specs/03-secrets-credentials.md §2."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from ar_common.errors import NotFoundError
from ar_domain.secrets.crypto import decrypt_envelope, encrypt_envelope
from ar_domain.secrets.models import EncryptedSecret

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession


class DbEncryptedStore:
    """AES-256-GCM values in ``encrypted_secrets``, DEK wrapped by a KEK."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        keyring: dict[str, bytes],
        active_key_id: str,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.keyring = keyring
        self.active_key_id = active_key_id

    async def put(self, path: str, value: bytes, *, aad: bytes) -> None:
        kek = self._kek(self.active_key_id)
        wrapped, nonce, ciphertext = encrypt_envelope(value, kek, aad=aad)
        existing = await self._row(path)
        if existing is None:
            self.session.add(
                EncryptedSecret(
                    id=_path_id(path),
                    tenant_id=self.tenant_id,
                    key_id=self.active_key_id,
                    wrapped_dek=wrapped,
                    nonce=nonce,
                    ciphertext=ciphertext,
                )
            )
        else:
            existing.key_id = self.active_key_id
            existing.wrapped_dek = wrapped
            existing.nonce = nonce
            existing.ciphertext = ciphertext
        await self.session.flush()

    async def get(self, path: str, *, aad: bytes) -> bytes:
        row = await self._row(path)
        if row is None:
            raise NotFoundError("secret value not found")
        kek = self._kek(row.key_id)
        return decrypt_envelope(
            wrapped_dek=row.wrapped_dek,
            nonce=row.nonce,
            ciphertext=row.ciphertext,
            kek=kek,
            aad=aad,
        )

    async def delete(self, path: str) -> None:
        row = await self._row(path)
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()

    async def rewrap_all(self, *, aad_for: Callable[[EncryptedSecret], bytes]) -> int:
        """Re-encrypt every row with the active KEK."""
        rows = (
            await self.session.scalars(
                select(EncryptedSecret).where(EncryptedSecret.tenant_id == self.tenant_id)
            )
        ).all()
        count = 0
        for row in rows:
            if row.key_id == self.active_key_id:
                continue
            aad = aad_for(row)
            plaintext = decrypt_envelope(
                wrapped_dek=row.wrapped_dek,
                nonce=row.nonce,
                ciphertext=row.ciphertext,
                kek=self._kek(row.key_id),
                aad=aad,
            )
            wrapped, nonce, ciphertext = encrypt_envelope(
                plaintext, self._kek(self.active_key_id), aad=aad
            )
            row.key_id = self.active_key_id
            row.wrapped_dek = wrapped
            row.nonce = nonce
            row.ciphertext = ciphertext
            count += 1
        await self.session.flush()
        return count

    def _kek(self, key_id: str) -> bytes:
        kek = self.keyring.get(key_id)
        if kek is None:
            raise NotFoundError(f"encryption key {key_id} is not in the ring")
        return kek

    async def _row(self, path: str) -> EncryptedSecret | None:
        return await self.session.get(EncryptedSecret, _path_id(path))


def _path_id(path: str) -> uuid.UUID:
    try:
        return uuid.UUID(path)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, path)
