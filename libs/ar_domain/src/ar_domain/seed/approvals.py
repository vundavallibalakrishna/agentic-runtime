"""Dev-seed approval policy so a fresh tenant can finish a W2 write.

Spec 09 leaves an empty rule set on requester mode. The seeded assistant is
owned by ``admin@dev.local``, who is also the usual requester. Segregation of
duties then blocks that owner, and nobody else is eligible, so the approval
never completes. This policy names the seeded approver (and the owner, so the
owner's attempt still reaches that check and returns ``sod_violation``).
"""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING, Any

import orjson
from sqlalchemy import select

from ar_common.time import utcnow
from ar_domain.demo_ids import demo_id
from ar_domain.identity.models import Group, GroupMember
from ar_domain.policy.models import Policy, PolicyVersion

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

POLICY_NAME = "Seeded write approval"
POLICY_MESSAGE = "A second person approves this write."
GROUP_NAME = "approvers"
_PRIORITY = 1000


def write_approval_document(*, approver_id: uuid.UUID, owner_id: uuid.UUID) -> dict[str, object]:
    """Rules document. Users mode lists the approver first, then the owner."""
    return {
        "rules": [
            {
                "id": "seeded-w2-second-person",
                "effect": "require_approval",
                "message": POLICY_MESSAGE,
                "match": {"risk_classes": ["W2"]},
                "approval": {
                    "approvers": {
                        "mode": "users",
                        "groups": [GROUP_NAME],
                        "users": [str(approver_id), str(owner_id)],
                    },
                    "required_approvals": 1,
                    "four_eyes": False,
                    "step_up": False,
                    "ttl_s": 86400,
                },
            }
        ]
    }


def install_seeded_write_policy(
    store: Any, tenant_id: uuid.UUID, *, approver_id: uuid.UUID, owner_id: uuid.UUID
) -> uuid.UUID:
    """Put the seed policy on a process cache. A second call keeps the first row."""
    policies = store.policies
    for row in policies.values():
        if (
            isinstance(row, dict)
            and row.get("tenant_id") == tenant_id
            and row.get("name") == POLICY_NAME
        ):
            found = row.get("id")
            if isinstance(found, uuid.UUID):
                return found
    policy_id = demo_id("policy-seeded-w2")
    version_id = demo_id("policy-seeded-w2-v1")
    now = utcnow()
    document = write_approval_document(approver_id=approver_id, owner_id=owner_id)
    store.policy_versions[version_id] = {
        "id": version_id,
        "tenant_id": tenant_id,
        "policy_id": policy_id,
        "version": 1,
        "document": document,
        "rego": None,
        "hash": _hash(document),
        "test_report": {"passed": True, "failed": []},
        "created_by": owner_id,
        "created_at": now,
    }
    policies[policy_id] = {
        "id": policy_id,
        "tenant_id": tenant_id,
        "name": POLICY_NAME,
        "description": _description(),
        "kind": "rules",
        "status": "active",
        "priority": _PRIORITY,
        "active_version_id": version_id,
        "created_by": owner_id,
        "created_at": now,
        "updated_at": now,
    }
    return policy_id


async def apply(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    admin_id: uuid.UUID,
    approver_id: uuid.UUID,
) -> None:
    """Insert the approvers group and the active W2 policy. Safe to run twice."""
    await _group(session, tenant_id, approver_id)
    existing = await session.scalar(
        select(Policy).where(Policy.tenant_id == tenant_id, Policy.name == POLICY_NAME)
    )
    if existing is not None:
        return
    policy_id = demo_id("policy-seeded-w2")
    version_id = demo_id("policy-seeded-w2-v1")
    now = utcnow()
    document = write_approval_document(approver_id=approver_id, owner_id=admin_id)
    session.add(
        Policy(
            id=policy_id,
            tenant_id=tenant_id,
            name=POLICY_NAME,
            description=_description(),
            kind="rules",
            status="active",
            priority=_PRIORITY,
            created_by=admin_id,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()
    session.add(
        PolicyVersion(
            id=version_id,
            tenant_id=tenant_id,
            policy_id=policy_id,
            version=1,
            document=document,
            rego=None,
            hash=_hash(document),
            test_report={"passed": True, "failed": []},
            created_by=admin_id,
            created_at=now,
        )
    )
    await session.flush()
    stored = await session.get(Policy, policy_id)
    if stored is not None:
        stored.active_version_id = version_id
        stored.updated_at = now


def _description() -> str:
    return (
        "Fresh-seed default for writes. approver@dev.local is in the approvers group "
        "and can decide. The owner is also listed so a self-approval reaches segregation "
        "of duties (sod_violation) instead of leaving the call with no eligible approver."
    )


def _hash(document: dict[str, object]) -> str:
    return hashlib.sha256(orjson.dumps(document, option=orjson.OPT_SORT_KEYS)).hexdigest()


async def _group(session: AsyncSession, tenant_id: uuid.UUID, approver_id: uuid.UUID) -> None:
    group = await session.scalar(
        select(Group).where(Group.tenant_id == tenant_id, Group.name == GROUP_NAME)
    )
    if group is None:
        group = Group(
            id=demo_id("group-approvers"),
            tenant_id=tenant_id,
            name=GROUP_NAME,
            source="local",
            external_id=GROUP_NAME,
        )
        session.add(group)
        await session.flush()
    member = await session.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == approver_id,
        )
    )
    if member is None:
        session.add(GroupMember(tenant_id=tenant_id, group_id=group.id, user_id=approver_id))
