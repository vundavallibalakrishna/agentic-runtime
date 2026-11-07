"""Run the M33c tool-choice gym. See docs/testing/m33c-checklist.md.

The gym scores which tool a chat model picks. It runs on the demo tenant, which this
tooling builds through ``ar_testing`` (the gym itself holds no demo-tenant building,
M38b-T04d). The demo store it hands the gym already has the embedding model the handbook
needs and an in-memory object store for the gym's uploads. The cert key is read from the
environment and is never printed.
"""

from ar_domain.evals.gym.cli import main
from ar_testing.demo import demo_store

if __name__ == "__main__":
    raise SystemExit(main(make_store=demo_store))
