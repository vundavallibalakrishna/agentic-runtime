"""Choose the process store. Production boot refuses the in-memory double."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from ar_common.settings import uses_shared_process_state

if TYPE_CHECKING:
    from ar_common.settings import BaseServiceSettings
    from ar_domain.chat.service import ChatService
    from ar_domain.readmodel.model import RepositoryReadModel


class MemoryStoreRefusedError(RuntimeError):
    """``ChatService`` is a test double and must not boot in staging or production."""


def refuse_memory_double() -> None:
    """Raise when this process is staging or production.

    Unit tests and dev/CI construct ``ChatService`` directly. Production
    composition uses ``build_product_store``, which never calls it.
    """
    from ar_common.settings import get_settings  # noqa: PLC0415

    if os.environ.get("AR_BOOTSTRAP_WRITER") == "1":
        return
    if uses_shared_process_state(get_settings().env):
        raise MemoryStoreRefusedError(
            "ChatService is an in-memory test double. "
            "Staging and production read and write through Postgres repositories."
        )


def build_product_store(
    settings: BaseServiceSettings, *, starts_sandboxes: bool = False, **options: Any
) -> ChatService | RepositoryReadModel:
    """The store this process boots with. Production is the repository read model.

    ``starts_sandboxes`` is set by the sandbox manager only. Every other process is told
    here where computers come from, so no entry point can forget it.
    """
    store: ChatService | RepositoryReadModel
    if uses_shared_process_state(settings.env):
        from ar_domain.process_state import install_shared_state  # noqa: PLC0415
        from ar_domain.readmodel.model import RepositoryReadModel  # noqa: PLC0415

        store = RepositoryReadModel.from_settings(settings, **options)
        # Every process that serves or runs tools counts against the shared windows, so
        # the Valkey books are attached here and not left to each entry point.
        install_shared_state(store, settings)
    else:
        from ar_domain.chat.service import ChatService  # noqa: PLC0415

        store = ChatService(**options)
    if not starts_sandboxes:
        from ar_domain.sandboxes.manager_launch import register_sandbox_client  # noqa: PLC0415

        register_sandbox_client(store, settings)
    return store
