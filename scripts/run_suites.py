"""Score the repository eval suites against the demo tenant. ``make eval``.

The suites run on the demo tenant, which this tooling builds through ``ar_testing`` (the
eval command holds no demo-tenant building, M38b-T04d). A suite is scored by running the
agent, so it needs a model: set ``AR_CERT_LLM_API_KEY`` (and optionally
``AR_CERT_LLM_BASE_URL`` / ``AR_CERT_LLM_MODEL``). Without a key it scores nothing.

    uv run python scripts/run_suites.py run evals/golden evals/redteam
"""

import sys

from ar_system.evals.cli import main
from ar_testing.demo import demo_store

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], make_store=demo_store))
