"""Effective permissions. Spec: docs/06-security/authn-authz.md §1 and §4."""

import uuid  # noqa: TC003
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RoleGrant:
    """One assignment already joined to its role's permission list."""

    principal_type: str
    principal_id: uuid.UUID
    role_key: str
    permissions: tuple[str, ...]
    scope_type: str
    scope_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class EffectiveAccess:
    """Tenant-wide permissions, team-scoped permissions, and role keys."""

    permissions: frozenset[str]
    team_permissions: frozenset[tuple[uuid.UUID, str]]
    roles: frozenset[str]


def resolve_access(
    user_id: uuid.UUID,
    *,
    group_ids: set[uuid.UUID],
    team_ids: set[uuid.UUID],
    grants: list[RoleGrant],
) -> EffectiveAccess:
    """Union direct, group, and team grants.

    Team-scoped grants apply only inside that team. Tenant-scoped grants apply
    everywhere in the tenant.
    """
    permissions: set[str] = set()
    team_permissions: set[tuple[uuid.UUID, str]] = set()
    roles: set[str] = set()
    for grant in grants:
        matched = _matches(grant, user_id, group_ids, team_ids)
        if not matched:
            continue
        roles.add(grant.role_key)
        if grant.scope_type == "team" and grant.scope_id is not None:
            for permission in grant.permissions:
                team_permissions.add((grant.scope_id, permission))
            continue
        permissions.update(grant.permissions)
    return EffectiveAccess(
        permissions=frozenset(permissions),
        team_permissions=frozenset(team_permissions),
        roles=frozenset(roles),
    )


def _matches(
    grant: RoleGrant,
    user_id: uuid.UUID,
    group_ids: set[uuid.UUID],
    team_ids: set[uuid.UUID],
) -> bool:
    if grant.principal_type == "user":
        return grant.principal_id == user_id
    if grant.principal_type == "group":
        return grant.principal_id in group_ids
    if grant.principal_type == "team":
        return grant.principal_id in team_ids
    return False
