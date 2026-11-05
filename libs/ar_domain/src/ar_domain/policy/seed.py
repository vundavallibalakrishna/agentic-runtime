"""Dev-seed rows for the policy tables. Spec: docs/03-specs/09-policy-approvals.md."""

import hashlib
import uuid  # noqa: TC003
from typing import TYPE_CHECKING

import orjson
from sqlalchemy import select

from ar_common.time import utcnow
from ar_domain.demo_ids import demo_id
from ar_domain.policy.models import Policy, PolicyVersion

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_seeded_write_policy(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    admin_id: uuid.UUID,
    name: str,
    description: str,
    priority: int,
    document: dict[str, object],
) -> None:
    """Insert one active rules policy. A second call keeps the existing row."""
    existing = await session.scalar(
        select(Policy).where(Policy.tenant_id == tenant_id, Policy.name == name)
    )
    if existing is not None:
        return
    policy_id = demo_id("policy-seeded-w2")
    version_id = demo_id("policy-seeded-w2-v1")
    now = utcnow()
    session.add(
        Policy(
            id=policy_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            kind="rules",
            status="active",
            priority=priority,
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
            hash=hashlib.sha256(orjson.dumps(document, option=orjson.OPT_SORT_KEYS)).hexdigest(),
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
