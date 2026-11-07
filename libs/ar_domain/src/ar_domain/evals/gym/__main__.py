"""The gym needs a seeded tenant from tooling; run it through the script.

The gym holds no demo-tenant building (M38b-T04d), so it is not started directly. Run
``scripts/m33c_eval_gym.py`` (``make eval-gym``), which builds the demo tenant and the
embedding model the world needs and then calls ``ar_domain.evals.gym.cli.main``.
"""

import sys

if __name__ == "__main__":
    sys.stderr.write("run the gym through scripts/m33c_eval_gym.py (make eval-gym)\n")
    raise SystemExit(2)
