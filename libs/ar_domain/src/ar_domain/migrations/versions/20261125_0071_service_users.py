"""A service account owns what it creates through a user of its own.

Revision ID: 0071
Revises: 0070
Create Date: 2026-11-25

Files, documents, conversations and runs are owned by a row of ``users``. A service
account is not one, so anything its key created failed on the owner's foreign key: an
upload, a conversation and a run all answered 500. Each service account now has a user
with the same id and ``kind = 'service'``. It has no password and no way to sign in, and
is not listed with the people of the workspace.

``users.kind`` is ``person`` for every existing row. Each existing service account is
given its user. Downgrade removes those users and the column; it refuses while one of
them owns anything, since the rows it owns would be deleted with it.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0071"
down_revision: str | None = "0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("kind", sa.Text(), nullable=False, server_default=sa.text("'person'"))
    )
    op.create_check_constraint("kind", "users", "kind IN ('person','service')")
    op.execute(
        sa.text(
            "INSERT INTO users (id, tenant_id, idp_subject, email, display_name, status, kind) "
            "SELECT id, tenant_id, 'service:' || id::text, id::text || '@service.invalid', name, "
            "CASE status WHEN 'active' THEN 'active' ELSE 'suspended' END, 'service' "
            "FROM service_accounts ON CONFLICT (id) DO NOTHING"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    owned = bind.execute(
        sa.text(
            "SELECT count(*) FROM users u WHERE u.kind = 'service' AND ("
            "EXISTS (SELECT 1 FROM files f WHERE f.owner_user_id = u.id) OR "
            "EXISTS (SELECT 1 FROM conversations c WHERE c.user_id = u.id) OR "
            "EXISTS (SELECT 1 FROM runs r WHERE r.user_id = u.id))"
        )
    ).scalar()
    if owned:
        raise RuntimeError("cannot remove service users while one owns files or conversations")
    op.execute(sa.text("DELETE FROM users WHERE kind = 'service'"))
    op.drop_constraint(op.f("ck_users_kind"), "users", type_="check")
    op.drop_column("users", "kind")
