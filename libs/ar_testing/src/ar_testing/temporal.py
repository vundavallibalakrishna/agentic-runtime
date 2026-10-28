"""Time-skipping Temporal test environment."""

import asyncio
from typing import TYPE_CHECKING

import pytest
from temporalio.testing import WorkflowEnvironment

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
async def temporal_env() -> AsyncIterator[WorkflowEnvironment]:
    """Start a time-skipping workflow environment.

    The SDK downloads a test server on first use. A truncated archive is
    retried instead of failing the whole integration job.
    """
    env: WorkflowEnvironment | None = None
    last_error: RuntimeError | None = None
    for attempt in range(3):
        try:
            env = await WorkflowEnvironment.start_time_skipping()
            break
        except RuntimeError as exc:
            last_error = exc
            if "ephemeral server download" not in str(exc) or attempt == 2:
                raise
            await asyncio.sleep(1 + attempt)
    if env is None:
        raise RuntimeError("Temporal test server did not start") from last_error
    async with env:
        yield env
