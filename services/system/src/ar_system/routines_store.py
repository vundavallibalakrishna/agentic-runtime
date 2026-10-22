"""Process store the system worker activities share."""

_STORE: object | None = None


def bind_store(store: object) -> None:
    """Point routine activities at the process store."""
    global _STORE  # noqa: PLW0603
    _STORE = store


def current_store() -> object:
    if _STORE is None:
        raise RuntimeError("routine store is not bound")
    return _STORE
