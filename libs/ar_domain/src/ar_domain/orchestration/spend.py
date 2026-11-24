"""What the agents one agent called have spent, counted as they spend it.

An agent's budget covers the agents it calls. Each of them is given what the caller has
left when it starts, and several started together would each be given all of it. So the
caller keeps one pool for a call, every agent in that call draws from it as it runs, and
the pool says when it is empty. The caller is then charged what the pool recorded, which
includes the spend of an agent that was stopped for running out of time.

That count is for agents run inside the caller's step, in one process. On a worker each
called agent is its own workflow, perhaps on another worker: the pool is then on each
run's request, and ``pool_limit`` adds up what the runs of the call have saved as spent.
"""

from __future__ import annotations

from ar_domain.runs.request import asked

# The counts of the called agents that are running now, by run id. A count lives for one
# call and is dropped when the call ends. It is working state of the step that made the
# call, like the step's own counters, and is never stored on the run: a run row is saved
# and returned by the API as it is.
_RUNNING: dict[str, Spend] = {}
_ENDED = frozenset({"completed", "failed", "cancelled", "budget_exceeded"})


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


def pool_limit(run: dict[str, object], store: object = None) -> str | None:
    """The limit the caller's pool has passed, for a run that draws on one.

    A called agent run inside its caller's step counts in this process. One that is its
    own workflow has the pool on its request, and reads what every run of the same call
    has saved as spent: any worker gets the same answer from the same rows.
    """
    own = spend_of(run)
    if own is not None:
        return own.over()
    shared = asked(run, "pool")
    runs = getattr(store, "runs", None)
    if not isinstance(shared, dict) or not isinstance(runs, dict):
        return None
    tokens = cost = 0
    for row in runs.values():
        if not isinstance(row, dict) or row.get("parent_run_id") != run.get("parent_run_id"):
            continue
        theirs = asked(row, "pool")
        if isinstance(theirs, dict) and theirs.get("call") == shared.get("call"):
            spent = spent_so_far(row)
            tokens += spent[0]
            cost += spent[1]
    if tokens > _whole(shared.get("tokens")):
        return "max_tokens"
    if cost > _whole(shared.get("cost")):
        return "max_cost_micros"
    return None


def spent_so_far(run: dict[str, object]) -> tuple[int, int]:
    """Budget tokens and cost a run has used, from what it last saved.

    While a run goes a step at a time its counts are on its checkpoint. Once it has
    ended they are on its usage. Both include what the agents it called used.
    """
    checkpoint = run.get("checkpoint")
    loop = checkpoint.get("worker_loop") if isinstance(checkpoint, dict) else None
    if isinstance(loop, dict) and str(run.get("status")) not in _ENDED:
        return _whole(loop.get("tokens")), _whole(loop.get("cost"))
    usage = run.get("usage")
    used = usage if isinstance(usage, dict) else {}
    called = used.get("subagents")
    theirs = called if isinstance(called, dict) else {}
    tokens = sum(
        _whole(source.get(key)) for source in (used, theirs) for key in ("tokens_in", "tokens_out")
    )
    return tokens, _whole(used.get("cost_micros"))


def _whole(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0
