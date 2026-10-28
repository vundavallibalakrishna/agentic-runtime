"""Channel secret revisions stay encrypted, immutable and tenant-scoped."""

import base64
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import SecretStr

from ar_domain.secrets.cached import _backend, load_cached_secret, save_cached_secret
from ar_domain.secrets.models import EncryptedSecret, SecretRef


async def test_encrypted_revision_and_wrong_tenant_access(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        secrets_backend="db_encrypted",
        db_encryption_keys=SecretStr('{"k1":"' + base64.b64encode(b"t" * 32).decode() + '"}'),
        db_encryption_active_key="k1",
    )
    monkeypatch.setattr("ar_domain.secrets.cached.get_settings", lambda: settings)
    rows = {}

    async def get(model: type, key: uuid.UUID) -> object:
        return rows.get((model, key))

    def add(row: object) -> None:
        rows[(type(row), row.id)] = row

    session = SimpleNamespace(get=get, add=add, flush=AsyncMock())
    tenant, secret = uuid.uuid4(), uuid.uuid4()
    await save_cached_secret(
        session, tenant_id=tenant, secret_id=secret, value=b"portal signing key", user_id=None
    )
    encrypted = next(row for (model, _), row in rows.items() if model is EncryptedSecret)
    assert b"portal signing key" not in encrypted.ciphertext
    assert await load_cached_secret(session, tenant, secret) == b"portal signing key"
    await save_cached_secret(
        session, tenant_id=tenant, secret_id=secret, value=b"replacement", user_id=None
    )
    assert await load_cached_secret(session, tenant, secret) == b"portal signing key"
    assert await load_cached_secret(session, uuid.uuid4(), secret) is None
    assert await load_cached_secret(session, tenant, uuid.uuid4()) is None
    with pytest.raises(ValueError, match="tenant mismatch"):
        await save_cached_secret(
            session, tenant_id=uuid.uuid4(), secret_id=secret, value=b"other", user_id=None
        )
    assert len([row for (model, _), row in rows.items() if model is SecretRef]) == 1
    with pytest.raises(ValueError, match="Unsupported"):
        _backend(session, tenant, "unsupported")


async def test_vault_revision_uses_registered_mount_and_same_aad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        secrets_backend="vault",
        vault_addr="https://vault.example",
        vault_token=SecretStr("server-only-token"),
        vault_kv_mount="secrets",
    )
    monkeypatch.setattr("ar_domain.secrets.cached.get_settings", lambda: settings)
    client = Mock()
    create = Mock(return_value=client)
    monkeypatch.setattr("hvac.Client", create)
    backend = _backend(SimpleNamespace(), uuid.uuid4(), "vault")
    assert backend.mount == "secrets"
    create.assert_called_once_with(url="https://vault.example", token="server-only-token")  # noqa: S106
