"""Apply the product seed on the owner connection."""

import asyncio
import importlib

from sqlalchemy.ext.asyncio import AsyncSession

from ar_domain.db.engine import get_engine, owner_database_url
from ar_domain.identity.seed import user_id_for_email
from ar_domain.seed.m2 import apply as apply_m2
from ar_domain.seed.plans import apply as apply_rows

_MODEL_MODULES = (
    "ar_domain.agents.tables",
    "ar_domain.audit.models",
    "ar_domain.conversations.tables",
    "ar_domain.events.models",
    "ar_domain.files.tables",
    "ar_domain.knowledge.tables",
    "ar_domain.identity.models",
    "ar_domain.models.tables",
    "ar_domain.secrets.models",
    "ar_domain.tools.tables",
    "ar_domain.usage.tables",
)


def import_models() -> None:
    """Register every mapped table before a flush.

    ``model_providers.api_key_ref_id`` references ``secret_refs``. Importing only
    the model registry leaves that table out of metadata and the flush fails.
    """
    for name in _MODEL_MODULES:
        importlib.import_module(name)


async def apply() -> None:
    """Seed plans, roles, the dev tenant, fake-llm and the assistant."""
    import_models()
    engine = get_engine(owner_database_url())
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        tenant_id = await apply_rows(session)
        admin_id = await user_id_for_email(session, tenant_id, "admin@dev.local")
        await apply_m2(session, tenant_id, admin_id)


def main() -> None:
    """Console entry used by ``scripts/seed.py``."""
    asyncio.run(apply())
