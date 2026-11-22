"""A request that waits for a worker answers when the wait ends, however it ends."""

import asyncio

import pytest
from temporalio.service import RPCError, RPCStatusCode

from ar_domain.durable.waiting import worker_result


class _Handle:
    def __init__(self, outcome: object, delay: float = 0.0) -> None:
        self.outcome = outcome
        self.delay = delay

    async def result(self) -> object:
        await asyncio.sleep(self.delay)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_a_finished_workflow_returns_its_result() -> None:
    assert asyncio.run(worker_result(_Handle({"status": "ready"}), 1)) == (
        True,
        {"status": "ready"},
    )


def test_a_wait_that_runs_out_is_not_finished() -> None:
    assert asyncio.run(worker_result(_Handle(None, delay=1), 0.01)) == (False, None)


@pytest.mark.parametrize(
    "status",
    [RPCStatusCode.DEADLINE_EXCEEDED, RPCStatusCode.CANCELLED, RPCStatusCode.UNAVAILABLE],
)
def test_a_long_poll_the_service_ended_is_not_finished(status: RPCStatusCode) -> None:
    ended = RPCError("context deadline exceeded", status, b"")
    assert asyncio.run(worker_result(_Handle(ended), 1)) == (False, None)


def test_any_other_service_error_is_raised() -> None:
    with pytest.raises(RPCError):
        asyncio.run(worker_result(_Handle(RPCError("gone", RPCStatusCode.NOT_FOUND, b"")), 1))
