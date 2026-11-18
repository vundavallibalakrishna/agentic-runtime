"""Clear the owner of the agents every tenant has.

Revision ID: 0052
Revises: 0051
Create Date: 2026-11-18

The assistant and the builder ship with the product. Their rows recorded whoever the
tenant seed ran for as owner, usually the administrator, and separation of duties stops
the owner of an agent signing off that agent's work. So the administrator could never
accept a reply from the assistant, although they did not write it. A built-in agent now
has no owner (OQ-145); new tenants are seeded that way and this revision clears the
owner on the rows that already exist, in every tenant.

Data only: ``agents.owner_user_id`` was always nullable, so older code keeps reading
these rows while pods roll. The owning team and the visibility are left as they are;
they say who may see the agent, not who wrote it. The slugs are written out here, so
this revision keeps meaning the same thing whatever the product later ships; a unit test
holds them equal to ``ar_domain.agents.logic.BUILTIN_AGENT_SLUGS`` for this release.

Forward-only. The earlier owner is not kept anywhere, so downgrade cannot put it back
and leaves the rows as they are. Code from before this revision reads an agent with no
owner without trouble. Restart API and worker processes after the migration so they
load the rows again.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The agents the tenant seed creates, as they are in this release.
BUILTIN_SLUGS: tuple[str, ...] = ("assistant", "builder")

# One row per built-in per tenant, so the statement stays small however many tenants
# there are. An agent a person built keeps its owner.
CLEAR_OWNER = (
    "UPDATE agents SET owner_user_id = NULL WHERE slug IN :slugs AND owner_user_id IS NOT NULL"
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(CLEAR_OWNER).bindparams(sa.bindparam("slugs", expanding=True)),
        {"slugs": list(BUILTIN_SLUGS)},
    )


def downgrade() -> None:
    """Forward-only. Who owned a built-in agent before is not recorded anywhere."""
