"""Re-embed memory facts after the embed alias changes. Spec: docs/03-specs/11-memory.md §6."""

import argparse
import os

from ar_domain.knowledge.embedder import embed_texts
from ar_domain.memory.logic import dimensions


def reembed(contents: list[str], *, model: str) -> list[list[float]]:
    """Return one vector per fact. The caller writes ``embedding_model_id``."""
    if not contents:
        return []
    return embed_texts(contents, model=model, dimensions=dimensions())


def main() -> None:
    """``--tenant`` selects the tenant. Without a database the dev store is process-local."""
    parser = argparse.ArgumentParser(description="Re-embed memory facts for one tenant")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--model", default="embed")
    args = parser.parse_args()
    if not os.environ.get("AR_DATABASE_URL", "").strip():
        print(f"tenant {args.tenant}: process store, nothing to re-embed")
        return
    print(f"tenant {args.tenant}: database re-embed uses model {args.model}")


if __name__ == "__main__":
    main()
