"""What the agents one agent called have spent, counted as they spend it.

An agent's budget covers the agents it calls. Each of them is given what the caller has
left when it starts, and several started together would each be given all of it. So the
caller keeps one pool for a call, every agent in that call draws from it as it runs, and
the pool says when it is empty. The caller is then charged what the pool recorded, which
includes the spend of an agent that was stopped for running out of time.
"""

from __future__ import annotations

# The counts of the called agents that are running now, by run id. A count lives for one
# call and is dropped when the call ends. It is working state of the step that made the
# call, like the step's own counters, and is never stored on the run: a run row is saved
# and returned by the API as it is.
_RUNNING: dict[str, Spend] = {}


class Spend:
    """A count of budget tokens and cost, with a ceiling and an optional pool above it."""

    def __init__(self, tokens_left: int, cost_left: int, pool: Spend | None = None) -> None:
        self.tokens_left = tokens_left
        self.cost_left = cost_left
        self.pool = pool
        self.tokens = 0
        self.cost = 0
        # What the model reported for this run's own calls, for the record of a run that
        # is stopped before it writes its usage.
        self.tokens_in = 0
        self.tokens_out = 0

    def add(self, tokens: int, cost: int) -> None:
        self.tokens += max(0, tokens)
        self.cost += max(0, cost)
        if self.pool is not None:
            self.pool.add(tokens, cost)

    def over(self) -> str | None:
        """The limit this count, or a pool above it, has passed. None while there is room."""
        if self.tokens > self.tokens_left:
            return "max_tokens"
        if self.cost > self.cost_left:
            return "max_cost_micros"
        return None if self.pool is None else self.pool.over()


def meter(run: dict[str, object], pool: Spend) -> Spend:
    """Give a called agent's run its own count, drawing on the caller's pool."""
    own = Spend(pool.tokens_left - pool.tokens, pool.cost_left - pool.cost, pool)
    _RUNNING[str(run.get("id"))] = own
    return own


def spend_of(run: dict[str, object]) -> Spend | None:
    return _RUNNING.get(str(run.get("id")))


def release(run: dict[str, object]) -> None:
    """Forget a called agent's count once its call has ended and been recorded."""
    _RUNNING.pop(str(run.get("id")), None)


def charge(
    run: dict[str, object], tokens: int, cost: int, *, tokens_in: int = 0, tokens_out: int = 0
) -> None:
    """Count what this run just spent. A run nobody called has nothing to count against.

    ``tokens`` is what the budget counts. ``tokens_in`` and ``tokens_out`` are what the
    model reported for one of this run's own calls.
    """
    own = spend_of(run)
    if own is not None:
        own.add(tokens, cost)
        own.tokens_in += max(0, tokens_in)
        own.tokens_out += max(0, tokens_out)


def pool_limit(run: dict[str, object]) -> str | None:
    """The limit the caller's pool has passed, for a run that draws on one."""
    own = spend_of(run)
    return None if own is None else own.over()
