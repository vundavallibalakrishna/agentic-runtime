"""Service-account permission resolution. Stage B of M42.

Spec: docs/06-security/authn-authz.md §2.
"""

from __future__ import annotations

import uuid

from ar_domain.identity.resolver import RoleGrant, resolve_access


def _grant(principal_type: str, principal_id: uuid.UUID, *perms: str) -> RoleGrant:
    return RoleGrant(
        principal_type=principal_type,
        principal_id=principal_id,
        role_key="custom",
        permissions=perms,
        scope_type="tenant",
        scope_id=None,
    )


def test_service_account_grant_resolves_only_with_matching_sa_id() -> None:
    sa_id = uuid.uuid4()
    grants = [_grant("service_account", sa_id, "agents:read", "chat:use")]
    with_sa = resolve_access(sa_id, group_ids=set(), team_ids=set(), grants=grants, sa_id=sa_id)
    assert with_sa.permissions == frozenset({"agents:read", "chat:use"})
    # Without the sa_id (e.g. resolving as a user) the SA grant must not apply.
    without = resolve_access(uuid.uuid4(), group_ids=set(), team_ids=set(), grants=grants)
    assert without.permissions == frozenset()


def test_user_group_team_resolution_unaffected_by_sa_param() -> None:
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    other_sa = uuid.uuid4()
    grants = [
        _grant("user", user_id, "a"),
        _grant("group", group_id, "b"),
        _grant("service_account", other_sa, "c"),
    ]
    access = resolve_access(
        user_id, group_ids={group_id}, team_ids=set(), grants=grants, sa_id=uuid.uuid4()
    )
    # The user and group grants apply; the unrelated service-account grant does not.
    assert access.permissions == frozenset({"a", "b"})
