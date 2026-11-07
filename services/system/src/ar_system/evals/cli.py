"""Run repository suites. ``uv run python scripts/run_suites.py run evals/golden`` (make eval).

A suite is scored by running the agent, so the command needs a model. It reads the
certification variables: ``AR_CERT_LLM_API_KEY``, and optionally ``AR_CERT_LLM_BASE_URL``
and ``AR_CERT_LLM_MODEL``. Without a key it exits 2 and scores nothing.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from ar_common.logging import get_logger
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.evals.book import EvalBook
from ar_domain.evals.gym.live import LiveConfigError, install_live, live_settings
from ar_domain.evals.seed_suites import suite_name
from ar_domain.identity.permissions import PERMISSION_KEYS

if TYPE_CHECKING:
    from collections.abc import Callable

_log = get_logger("ar_system.evals")


def main(
    argv: list[str] | None = None,
    *,
    make_store: Callable[[], ChatService] | None = None,
) -> int:
    """Score the named suite files against the seeded assistant.

    ``make_store`` returns the seeded tenant the suites run on; the tooling that invokes
    this command builds it (`scripts/run_suites.py` via `ar_testing`), so no demo-tenant
    building lives in this product package (strict rules 1 & 3, M38b-T04d).
    """
    parser = argparse.ArgumentParser(prog="ar_system.evals.cli")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--agent-template", default="assistant")
    parser.add_argument("--model-alias", default="reasoning")
    args = parser.parse_args(argv)
    del args.agent_template, args.model_alias
    try:
        key, base_url, model = live_settings()
    except LiveConfigError:
        _log.error("model_required", detail="set AR_CERT_LLM_API_KEY to score a suite")
        return 2
    if make_store is None:
        _log.error("store_required", detail="run through scripts/run_suites.py (make eval)")
        return 2
    store = make_store()
    install_live(store, demo_id("tenant"), key=key, base_url=base_url, model=model)
    actor = Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
    )
    book = EvalBook(store)
    failed = 0
    for raw in args.paths:
        for file in _files(Path(raw)):
            suite_id = _suite_id(book, actor, file)
            if suite_id is None:
                _log.info("suite_missing", path=str(file))
                failed += 1
                continue
            run = book.start_run(actor, suite_id, {"agent_version_ref": "published"})
            raw_summary = run.get("summary")
            summary = raw_summary if isinstance(raw_summary, dict) else {}
            rate = summary.get("pass_rate")
            _log.info("suite_scored", path=str(file), pass_rate=rate, status=run.get("status"))
            if rate != 1:
                failed += 1
    return 1 if failed else 0


def _files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.glob("*.yaml"))
    return [path]


def _suite_id(book: EvalBook, actor: Actor, file: Path) -> uuid.UUID | None:
    try:
        name = suite_name(file)
    except OSError:
        return None
    for row in book.list_suites(actor):
        found = row.get("id")
        if str(row.get("name") or "") == name and isinstance(found, uuid.UUID):
            return found
    return None


if __name__ == "__main__":
    # The command runs on the demo tenant, which the tooling builds; it is not started
    # directly (M38b-T04d). Run scripts/run_suites.py (make eval).
    sys.stderr.write("run the suites through scripts/run_suites.py (make eval)\n")
    sys.exit(2)
