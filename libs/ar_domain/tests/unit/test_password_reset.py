"""A password reset is a stored row and a changed user row, through the identity store."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

import pytest

from ar_common.errors import ArError
from ar_common.time import utcnow
from ar_domain.db.context import Principal, TenantContext
from ar_domain.demo_ids import demo_id
from ar_domain.identity.passwords import verify_password
from ar_domain.identity.recovery import _hash, confirm_reset, request_reset, reset_link
from ar_testing.memory_identity import MemoryIdentityStore

if TYPE_CHECKING:
    from ar_domain.identity.service import IdentityStore

ADA = "admin@dev.local"


def _identity() -> tuple[MemoryIdentityStore, IdentityStore]:
    principal = Principal(kind="system", id="login", tenant_id=demo_id("tenant"))
    store = MemoryIdentityStore(TenantContext.from_principal(principal, "test"))
    return store, cast("IdentityStore", store)


async def test_a_reset_stores_only_the_hash_and_sets_the_new_password_once() -> None:
    memory, identity = _identity()
    token = await request_reset(identity, f"  {ADA.upper()} ")
    assert token
    [row] = memory.password_resets.values()
    assert row.token_hash == _hash(token)
    assert token not in {row.token_hash}
    assert row.used_at is None
    user = await confirm_reset(identity, token, "a-new-password")
    assert user.email == ADA
    assert verify_password(str(user.password_hash), "a-new-password")
    assert not verify_password(str(user.password_hash), "dev-password")
    assert user.password_set_at is not None
    assert row.used_at is not None
    with pytest.raises(ArError, match="not valid"):
        await confirm_reset(identity, token, "another-password")


async def test_an_address_that_cannot_sign_in_gets_no_token() -> None:
    memory, identity = _identity()
    assert await request_reset(identity, "nobody@dev.local") is None
    person = await identity.get_user_by_email(ADA)
    assert person is not None
    person.status = "suspended"
    assert await request_reset(identity, ADA) is None
    person.status = "active"
    person.password_hash = None
    assert await request_reset(identity, ADA) is None
    assert memory.password_resets == {}


async def test_a_bad_expired_or_short_reset_changes_nothing() -> None:
    memory, identity = _identity()
    token = await request_reset(identity, ADA)
    assert token
    person = await identity.get_user_by_email(ADA)
    assert person is not None
    before = person.password_hash
    with pytest.raises(ArError, match="at least 8 characters"):
        await confirm_reset(identity, token, "short")
    with pytest.raises(ArError, match="not valid"):
        await confirm_reset(identity, "not-a-token", "a-new-password")
    [row] = memory.password_resets.values()
    row.expires_at = utcnow() - timedelta(minutes=1)
    with pytest.raises(ArError, match="expired"):
        await confirm_reset(identity, token, "a-new-password")
    row.expires_at = utcnow() + timedelta(minutes=5)
    person.status = "suspended"
    with pytest.raises(ArError, match="not valid"):
        await confirm_reset(identity, token, "a-new-password")
    assert person.password_hash == before
    assert row.used_at is None


def test_the_link_is_built_on_the_installs_public_address() -> None:
    assert reset_link("https://works.example.org/", "abc") == (
        "https://works.example.org/reset-password?token=abc"
    )
