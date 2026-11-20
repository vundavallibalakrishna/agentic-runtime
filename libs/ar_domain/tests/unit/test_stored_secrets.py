"""A tool opens a tenant secret by its name from the rows loaded with the tenant."""

from __future__ import annotations

import base64
import uuid
from types import SimpleNamespace

import orjson
import pytest
from pydantic import SecretStr

from ar_common.errors import ConflictError, NotFoundError
from ar_common.settings import get_settings, set_settings
from ar_domain.db.context import Principal, TenantContext
from ar_domain.secrets.crypto import encrypt_envelope
from ar_domain.secrets.loaded import open_stored_secret
from ar_domain.tools.named_secrets import read_named_secret, write_named_secret
from ar_testing.memory_secrets import provider

_KEK = b"k" * 32


@pytest.fixture
def keyring() -> object:
    before = get_settings()
    ring = orjson.dumps({"k1": base64.b64encode(_KEK).decode()}).decode()
    set_settings(before.model_copy(update={"db_encryption_keys": SecretStr(ring)}))
    yield None
    set_settings(before)


def _row(tenant: uuid.UUID, name: str, value: str, **more: object) -> dict[str, object]:
    secret_id = uuid.uuid4()
    wrapped, nonce, ciphertext = encrypt_envelope(
        value.encode(), _KEK, aad=f"{tenant}:{secret_id}".encode()
    )
    return {
        "id": secret_id,
        "tenant_id": tenant,
        "name": name,
        "backend": "db_encrypted",
        "path": f"tenants/{tenant}/secrets/{secret_id}",
        "owner_user_id": None,
        "key_id": "k1",
        "wrapped_dek": wrapped,
        "nonce": memoryview(nonce),
        "ciphertext": ciphertext,
        **more,
    }


def _store(*rows: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(stored_secrets={row["id"]: row for row in rows}, named_secrets={})


def test_a_tool_opens_the_tenants_secret_by_name(keyring: object) -> None:
    del keyring
    tenant, other = uuid.uuid4(), uuid.uuid4()
    store = _store(_row(tenant, "vendor", "the-value"), _row(other, "theirs", "not-yours"))
    assert read_named_secret(store, tenant, "vendor") == "the-value"
    assert read_named_secret(store, tenant, "theirs") is None
    assert read_named_secret(store, other, "vendor") is None
    assert read_named_secret(store, tenant, "") is None
    assert open_stored_secret(SimpleNamespace(), tenant, "vendor") is None


def test_a_secret_the_product_keeps_for_itself_is_read_first(keyring: object) -> None:
    del keyring
    tenant = uuid.uuid4()
    store = _store(_row(tenant, "token", "from-the-secret-store"))
    write_named_secret(store, tenant, "token", "kept-by-the-product")
    assert read_named_secret(store, tenant, "token") == "kept-by-the-product"


def test_a_value_that_cannot_be_opened_is_a_missing_secret(keyring: object) -> None:
    del keyring
    tenant = uuid.uuid4()
    personal = _row(tenant, "mine", "personal", owner_user_id=uuid.uuid4())
    other_key = _row(tenant, "old-key", "x", key_id="k9")
    no_value = {**_row(tenant, "no-value", "x"), "ciphertext": None}
    damaged = _row(tenant, "damaged", "x")
    damaged["ciphertext"] = b"0" * 24
    moved = _row(tenant, "moved", "x")
    moved["id"] = uuid.uuid4()
    store = _store(personal, other_key, no_value, damaged, moved)
    store.stored_secrets["junk"] = "not a row"
    for name in ("mine", "old-key", "no-value", "damaged", "moved"):
        assert read_named_secret(store, tenant, name) is None


def test_an_unreachable_vault_is_a_missing_secret() -> None:
    tenant = uuid.uuid4()
    row = {**_row(tenant, "in-vault", "x"), "backend": "vault"}
    before = get_settings()
    set_settings(before.model_copy(update={"vault_addr": "http://127.0.0.1:1"}))
    try:
        assert read_named_secret(_store(row), tenant, "in-vault") is None
    finally:
        set_settings(before)


async def test_the_test_stand_in_keeps_one_tenants_secrets_apart() -> None:
    store = SimpleNamespace(named_secrets={})
    secrets = provider(store)
    tenant, other = uuid.uuid4(), uuid.uuid4()

    def ctx(tenant_id: uuid.UUID) -> TenantContext:
        principal = Principal(kind="system", id="system", tenant_id=tenant_id)
        return TenantContext(tenant_id, None, principal, "req-test")

    mine, theirs = secrets(ctx(tenant)), secrets(ctx(other))
    made = await mine.create("vendor", "generic", "first", "")
    with pytest.raises(ConflictError):
        await mine.create("vendor", "generic", "again", "")
    assert [row.name for row in await mine.list()] == ["vendor"]
    assert await theirs.list() == []
    with pytest.raises(NotFoundError):
        await theirs.get(made.id)
    assert read_named_secret(store, tenant, "vendor") == "first"
    assert (await mine.describe(made.id, "note")).description == "note"
    assert (await mine.rotate(made.id, "second")).version == 2
    assert read_named_secret(store, tenant, "vendor") == "second"
    await mine.delete(made.id)
    assert read_named_secret(store, tenant, "vendor") is None
    assert await mine.list() == []
