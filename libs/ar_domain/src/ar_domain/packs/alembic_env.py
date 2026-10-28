"""Build a pack Alembic environment. Spec: docs/04-data/migrations.md §6."""

from pathlib import Path


def alembic_env(pack_id: str, schema: str) -> dict[str, str]:
    """Return the environment names a pack migration uses.

    The version table is ``{schema}_alembic_version``. Core history is untouched.
    """
    return {
        "pack_id": pack_id,
        "schema": schema,
        "version_table": f"{schema}_alembic_version",
        "script_location": str(Path("packs") / pack_id),
    }
