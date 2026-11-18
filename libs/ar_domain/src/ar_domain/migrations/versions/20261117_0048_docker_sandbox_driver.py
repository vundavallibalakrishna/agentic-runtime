"""Sandboxes run on the docker driver.

Revision ID: 0048
Revises: 0047
Create Date: 2026-11-17

The install is one Docker Compose node. A row that named the removed driver is
stored as docker; the container it pointed at is gone.
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE sandboxes SET driver = 'docker' WHERE driver <> 'docker'")
    op.drop_constraint(op.f("ck_sandboxes_driver"), "sandboxes", type_="check")
    op.create_check_constraint(op.f("ck_sandboxes_driver"), "sandboxes", "driver IN ('docker')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_sandboxes_driver"), "sandboxes", type_="check")
    op.create_check_constraint(
        op.f("ck_sandboxes_driver"),
        "sandboxes",
        "driver IN ('docker','kubernetes')",
    )
