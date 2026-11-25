"""What a service account is for, in the words a person choosing would use.

A key can do nothing until its account holds a role, and a person who creates one should
not need to know the permission catalogue. Each capability names the built-in role that
grants it and the permissions a key made for it is narrowed to. The screen that creates an
account reads this list; nothing about roles is written in the screen.
"""

from __future__ import annotations

from typing import TypedDict

from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS


class Capability(TypedDict):
    key: str
    role: str
    permissions: list[str]


# The capability, the system role that grants it, and what a key for it may do.
_CAPABILITIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("chat", "member", ("chat:use", "agents:read")),
    ("knowledge_search", "member", ("knowledge:read",)),
    ("knowledge_manage", "knowledge_manager", ("knowledge:read", "knowledge:manage", "chat:use")),
    (
        "agents_manage",
        "builder",
        ("agents:read", "agents:create", "agents:edit", "agents:publish"),
    ),
)


def capabilities() -> list[Capability]:
    """Every capability whose role really grants each of its permissions."""
    found: list[Capability] = []
    for key, role, permissions in _CAPABILITIES:
        granted = set(SYSTEM_ROLE_PERMISSIONS.get(role, ()))
        if all(item in granted for item in permissions):
            found.append({"key": key, "role": role, "permissions": list(permissions)})
    return found
