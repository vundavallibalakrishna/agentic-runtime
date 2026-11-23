"""Accepting an invitation creates the person, with the password they chose and their roles."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

import pytest

from ar_common.errors import ArError, ConflictError, ValidationFailedError
from ar_common.time import utcnow
from ar_domain.db.context import Principal, TenantContext
from ar_domain.demo_ids import demo_id
from ar_domain.identity.passwords import verify_password
from ar_domain.identity.service import IdentityService
from ar_testing.memory_identity import MemoryIdentityStore

if TYPE_CHECKING:
    from ar_domain.identity.service import IdentityStore

NEW = "new.person@example.test"


def _service() -> tuple[MemoryIdentityStore, IdentityService]:
    principal = Principal(kind="system", id="login", tenant_id=demo_id("tenant"))
    store = MemoryIdentityStore(TenantContext.from_principal(principal, "test"))
    return store, IdentityService(cast("IdentityStore", store))


async def test_accepting_creates_the_person_with_their_roles_once() -> None:
    store, service = _service()
    [(invitation, token)] = await service.invite([NEW], ["member", "builder"])
    shown = await service.pending_invitation(token)
    assert shown.email == NEW
    user = await service.accept_invitation(token, "  New Person ", "a-good-password")
    assert (user.email, user.display_name, user.status) == (NEW, "New Person", "active")
    assert verify_password(str(user.password_hash), "a-good-password")
    assert user.password_set_at is not None
    assert await store.get_user_by_email(NEW) is user
    granted = {role.key for _row, role in await store.grants_for(user.id)}
    assert granted == {"member", "builder"}
    assert invitation.accepted_at is not None
    with pytest.raises(ArError, match="already been used"):
        await service.accept_invitation(token, "Again", "another-password")


async def test_a_person_with_no_name_is_called_by_their_address() -> None:
    _store, service = _service()
    [(_invitation, token)] = await service.invite([NEW], ["member"])
    user = await service.accept_invitation(token, "   ", "a-good-password")
    assert user.display_name == "new.person"


async def test_an_invitation_that_cannot_be_used_says_why_and_creates_nobody() -> None:
    store, service = _service()
    with pytest.raises(ArError, match="not valid"):
        await service.accept_invitation("not-a-token", "X", "a-good-password")
    [(invitation, token)] = await service.invite([NEW], ["member"])
    with pytest.raises(ValidationFailedError, match="at least 8 characters"):
        await service.accept_invitation(token, "X", "short")
    invitation.expires_at = utcnow() - timedelta(minutes=1)
    with pytest.raises(ArError, match="expired"):
        await service.accept_invitation(token, "X", "a-good-password")
    invitation.expires_at = utcnow() + timedelta(days=1)
    invitation.revoked_at = utcnow()
    with pytest.raises(ArError, match="not valid"):
        await service.accept_invitation(token, "X", "a-good-password")
    assert await store.get_user_by_email(NEW) is None
    assert invitation.accepted_at is None


async def test_an_invitation_cannot_change_the_password_of_an_existing_account() -> None:
    store, service = _service()
    [(invitation, token)] = await service.invite(["admin@dev.local"], ["member"])
    existing = await store.get_user_by_email("admin@dev.local")
    assert existing is not None
    before = existing.password_hash
    with pytest.raises(ConflictError, match="already has an account"):
        await service.accept_invitation(token, "Someone", "a-good-password")
    assert existing.password_hash == before
    assert invitation.accepted_at is None
