"""Register every mapped table. Each process calls this before its first ORM flush.

A flush resolves foreign keys through the shared metadata. A process that imported only
some table modules fails with ``NoReferencedTableError`` the first time it writes a row
whose parent table it never imported. The list is checked against the source tree by
``test_table_registry.py``.
"""

import importlib

TABLE_MODULES: tuple[str, ...] = (
    "ar_domain.agents.governance",
    "ar_domain.agents.tables",
    "ar_domain.approvals.models",
    "ar_domain.audit.models",
    "ar_domain.channels.tables",
    "ar_domain.connectors.tables",
    "ar_domain.conversations.tables",
    "ar_domain.documents.tables",
    "ar_domain.durability.tables",
    "ar_domain.evals.tables",
    "ar_domain.events.models",
    "ar_domain.exposure.tables",
    "ar_domain.files.tables",
    "ar_domain.identity.guest_tables",
    "ar_domain.identity.models",
    "ar_domain.knowledge.tables",
    "ar_domain.memory.tables",
    "ar_domain.models.tables",
    "ar_domain.orchestration.tables",
    "ar_domain.packs.tables",
    "ar_domain.policy.models",
    "ar_domain.records.tables",
    "ar_domain.routines.tables",
    "ar_domain.runs.tables",
    "ar_domain.sandboxes.tables",
    "ar_domain.secrets.models",
    "ar_domain.skills.tables",
    "ar_domain.tools.tables",
    "ar_domain.usage.tables",
)


def import_models() -> None:
    """Import each table module so foreign keys resolve. Safe to call many times."""
    for name in TABLE_MODULES:
        importlib.import_module(name)
