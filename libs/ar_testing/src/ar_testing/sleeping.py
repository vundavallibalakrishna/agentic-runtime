"""Replace a process-wide function for the test's own thread only.

Worker loops pause with ``asyncio.sleep``, and a test stops or speeds one up by replacing
it. The replacement is process-wide, and the stand-in model server runs its own loop on
another thread of the test process. Left unguarded, a replacement that raises ends that
server, and one that returns at once turns the server's idle loop into a tight loop that
never yields: every later call to the server then waits until it times out.
"""

import asyncio
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

_real_sleep = asyncio.sleep


def in_this_thread(
    replacement: Callable[..., Any], original: Callable[..., Any] | None = None
) -> Callable[..., Any]:
    """``replacement`` for the calling thread, and ``original`` for every other.

    ``original`` is the function being replaced. Left out, it is ``asyncio.sleep``.
    """
    owner = threading.get_ident()
    untouched = _real_sleep if original is None else original

    def call(*args: Any, **kwargs: Any) -> Any:
        chosen = replacement if threading.get_ident() == owner else untouched
        return chosen(*args, **kwargs)

    return call
