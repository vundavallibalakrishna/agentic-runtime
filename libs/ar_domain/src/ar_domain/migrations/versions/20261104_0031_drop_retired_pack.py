"""Drop the retired industry-pack schema.

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-04

The statements are safe on a database that never created the schema and on
one that already applied the retired pack revisions. Downgrade does not
recreate it.
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Schema name and version table belong to the retired pack. Core does not
# recreate them.
DROP_RETIRED_PACK: tuple[str, ...] = (
    "DROP SCHEMA IF EXISTS grc CASCADE",
    "DROP TABLE IF EXISTS public.grc_alembic_version",
    "DELETE FROM installed_pack_resources WHERE pack_row_id IN "
    "(SELECT id FROM installed_packs WHERE pack_id = 'grc')",
    "DELETE FROM installed_packs WHERE pack_id = 'grc'",
    "DELETE FROM tenant_pack_flags WHERE pack_id = 'grc'",
)


def upgrade() -> None:
    for statement in DROP_RETIRED_PACK:
        op.execute(statement)


def downgrade() -> None:
    """Forward-only. The retired schema is not rebuilt."""
