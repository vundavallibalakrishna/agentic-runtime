"""``python -m ar_ingest.cli migrate-store``."""

import argparse
import json

from ar_ingest.activities import migrate_activity
from ar_ingest.workflows.migrate_retrieval_store import MigrateRetrievalStoreWorkflow


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ar_ingest.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    migrate = sub.add_parser("migrate-store")
    migrate.add_argument("--collection-id", required=True)
    migrate.add_argument("--target", choices=["pgvector", "qdrant"], required=True)
    migrate.add_argument("--dry-run", action="store_true")
    migrate.add_argument("--rollback", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "migrate-store":
        print(  # noqa: T201
            json.dumps(
                {
                    "workflow": MigrateRetrievalStoreWorkflow.__name__,
                    "activity": migrate_activity.__name__,
                    "collection_id": args.collection_id,
                    "target": args.target,
                    "dry_run": args.dry_run,
                    "rollback": args.rollback,
                }
            )
        )


if __name__ == "__main__":
    main()
