"""Process store the system worker activities share."""

_STORE: object | None = None


def bind_store(store: object) -> None:
    """Point routine activities at the process store."""
    global _STORE  # noqa: PLW0603
    _STORE = store


def process_store() -> object:
    """The object boot bound. Ignores a request-scoped unit."""
    if _STORE is None:
        raise RuntimeError("routine store is not bound")
    return _STORE


def current_store() -> object:
    from ar_domain.readmodel.activity import active_unit  # noqa: PLC0415

    unit = active_unit()
    if unit is not None:
        return unit
    if _STORE is None:
        raise RuntimeError("routine store is not bound")
    return _STORE
