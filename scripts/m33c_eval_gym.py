"""Run the M33c tool-choice gym. See docs/testing/m33c-checklist.md.

The cert key is read from the environment and is never printed.
"""

from ar_domain.evals.gym.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
