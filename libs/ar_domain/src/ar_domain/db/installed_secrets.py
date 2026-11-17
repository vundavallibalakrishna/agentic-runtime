"""Staging and production password check shared by Alembic and bootstrap."""

from __future__ import annotations

import os

from ar_common.database_roles import assert_installed_database_secrets


def check_migration_secrets(database_url: str) -> None:
    """Refuse placeholder role passwords before Alembic connects."""
    assert_installed_database_secrets(os.environ.get("AR_ENV", "dev"), database_url)
