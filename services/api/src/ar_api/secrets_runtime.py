"""In-memory secret API used until a request has a database session.

The database-backed service is selected by ``AR_SECRETS_BACKEND`` inside
``ar_api.secrets_runtime``. This object is replaced in tests.
"""

import uuid

from ar_domain.secrets.service import SecretMetadata


class MemorySecretApi:
    """Metadata-only store. Plaintext is kept only to satisfy rotate/read tests."""

    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, SecretMetadata] = {}
        self._values: dict[uuid.UUID, str] = {}

    async def list(self) -> list[SecretMetadata]:
        return list(self._rows.values())

    async def create(self, name: str, kind: str, value: str, description: str) -> SecretMetadata:
        secret_id = uuid.uuid4()
        meta = SecretMetadata(secret_id, name, kind, 1, description, None)
        self._rows[secret_id] = meta
        self._values[secret_id] = value
        return meta

    async def get(self, secret_id: uuid.UUID) -> SecretMetadata | None:
        return self._rows.get(secret_id)

    async def update(self, secret_id: uuid.UUID, description: str) -> SecretMetadata | None:
        current = self._rows.get(secret_id)
        if current is None:
            return None
        updated = SecretMetadata(
            current.id,
            current.name,
            current.kind,
            current.version,
            description,
            current.owner_user_id,
        )
        self._rows[secret_id] = updated
        return updated

    async def delete(self, secret_id: uuid.UUID) -> None:
        self._rows.pop(secret_id, None)
        self._values.pop(secret_id, None)

    async def rotate(self, secret_id: uuid.UUID, value: str) -> SecretMetadata | None:
        current = self._rows.get(secret_id)
        if current is None:
            return None
        updated = SecretMetadata(
            current.id,
            current.name,
            current.kind,
            current.version + 1,
            current.description,
            current.owner_user_id,
        )
        self._rows[secret_id] = updated
        self._values[secret_id] = value
        return updated

    def value(self, secret_id: uuid.UUID) -> str | None:
        return self._values.get(secret_id)
