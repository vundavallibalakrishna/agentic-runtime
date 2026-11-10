"""Choose the process store. Production boot refuses the in-memory double."""

from __future__ import annotations

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

    if uses_shared_process_state(get_settings().env):
        raise MemoryStoreRefusedError(
            "ChatService is an in-memory test double. "
            "Staging and production read and write through Postgres repositories."
        )


def build_product_store(
    settings: BaseServiceSettings, **options: Any
) -> ChatService | RepositoryReadModel:
    """The store this process boots with. Production is the repository read model."""
    if uses_shared_process_state(settings.env):
        from ar_domain.readmodel.model import RepositoryReadModel  # noqa: PLC0415

        return RepositoryReadModel.from_settings(settings, **options)
    from ar_domain.chat.service import ChatService  # noqa: PLC0415

    return ChatService(**options)
