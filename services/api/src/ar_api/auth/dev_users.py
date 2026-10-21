"""The four seeded dev users. Stable ids match the in-process chat catalogue."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS
from ar_domain.identity.seed import DEV_USERS

DEV_TENANT_ID = demo_id("tenant")

_IDS = {
    "admin@dev.local": demo_id("admin"),
    "builder@dev.local": demo_id("builder"),
    "member@dev.local": demo_id("member"),
    "approver@dev.local": demo_id("approver"),
}


@dataclass(frozen=True, slots=True)
class DevUser:
    """One seeded person the dev login and the OIDC callback can sign in."""

    email: str
    display_name: str
    user_id: uuid.UUID
    roles: tuple[str, ...]
    permissions: frozenset[str]


def catalogue() -> dict[str, DevUser]:
    """Email to seeded user. Permissions are the union of the user's roles."""
    found: dict[str, DevUser] = {}
    for email, display_name, roles in DEV_USERS:
        permissions: set[str] = set()
        for role in roles:
            permissions.update(SYSTEM_ROLE_PERMISSIONS[role])
        found[email] = DevUser(
            email=email,
            display_name=display_name,
            user_id=_IDS[email],
            roles=roles,
            permissions=frozenset(permissions),
        )
    return found


def by_id(user_id: uuid.UUID) -> DevUser | None:
    """Return the seeded user for a stable demo id."""
    for user in catalogue().values():
        if user.user_id == user_id:
            return user
    return None
