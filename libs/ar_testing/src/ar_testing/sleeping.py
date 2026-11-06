"""Replace ``asyncio.sleep`` for the test's own thread only.

Worker loops pause with ``asyncio.sleep``, and a test stops or speeds one up by replacing
it. The replacement is process-wide, and the stand-in model server runs its own loop on
another thread: left unguarded, a replacement that raises ends that server for every
later test.
"""

import asyncio
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_real_sleep = asyncio.sleep


def in_this_thread(
    replacement: Callable[[float], Awaitable[None]],
) -> Callable[[float], Awaitable[None]]:
    """``replacement`` for the calling thread, and the real sleep for every other."""
    owner = threading.get_ident()

    async def sleep(seconds: float) -> None:
        if threading.get_ident() == owner:
            await replacement(seconds)
        else:
            await _real_sleep(seconds)

    return sleep
