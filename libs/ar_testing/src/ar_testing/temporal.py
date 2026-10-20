"""Time-skipping Temporal test environment."""

from typing import TYPE_CHECKING

import pytest
from temporalio.testing import WorkflowEnvironment

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
async def temporal_env() -> AsyncIterator[WorkflowEnvironment]:
    """Start a time-skipping workflow environment."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env
