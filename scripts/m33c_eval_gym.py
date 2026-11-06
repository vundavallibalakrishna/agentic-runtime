"""Run the M33c tool-choice gym. See docs/testing/m33c-checklist.md.

The gym scores which tool a chat model picks. Its handbook is a knowledge collection, so
the world needs an embedding model: this script registers the test stand-in for that.
The cert key is read from the environment and is never printed.
"""

from ar_domain.evals.gym.cli import main
from ar_testing.demo import connect_embeddings

if __name__ == "__main__":
    raise SystemExit(main(prepare=connect_embeddings))
