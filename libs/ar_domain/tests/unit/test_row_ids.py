"""A new row has its id as soon as it is made, so it can be named before it is saved."""

import uuid

from ar_domain.identity.models import ApiKey, RoleAssignment, ServiceAccount


def test_a_new_row_can_be_named_before_it_is_saved() -> None:
    tenant = uuid.uuid4()
    account = ServiceAccount(tenant_id=tenant, name="bot", description="")
    key = ApiKey(tenant_id=tenant, name="k", prefix="ak_x", secret_hash="h", scopes=[])  # noqa: S106
    grant = RoleAssignment(
        tenant_id=tenant,
        role_id=uuid.uuid4(),
        principal_type="service_account",
        principal_id=account.id,
        scope_type="tenant",
    )
    ids = [account.id, key.id, grant.id]
    assert all(isinstance(item, uuid.UUID) for item in ids)
    assert len(set(ids)) == 3


def test_an_id_that_was_given_is_kept() -> None:
    chosen = uuid.uuid4()
    account = ServiceAccount(id=chosen, tenant_id=uuid.uuid4(), name="bot", description="")
    assert account.id == chosen
