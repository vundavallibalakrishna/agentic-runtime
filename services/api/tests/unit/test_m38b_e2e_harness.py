"""The browser tests' API harness owns the demo tenant. Task: M38b-T04b."""

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

from ar_domain.demo_ids import demo_id

if TYPE_CHECKING:
    import pytest

HARNESS = Path(__file__).resolve().parents[1] / "support" / "e2e_server.py"


def test_the_harness_serves_the_product_app_over_the_demo_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    served: dict[str, object] = {}

    def run(app: object, **options: object) -> None:
        served["app"] = app
        served.update(options)

    # The harness says "no database" through the environment; undo that after the test.
    monkeypatch.setenv("AR_DURABLE_STATE", "postgres")
    monkeypatch.setenv("AR_PORT", "18999")
    spec = importlib.util.spec_from_file_location("e2e_server", HARNESS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.uvicorn, "run", run)

    module.main()

    store = served["app"].state.chat  # type: ignore[attr-defined]
    assert served["port"] == 18999
    assert served["host"] == "127.0.0.1"
    slugs = {str(row["slug"]) for row in store.agents.values()}
    assert {"assistant", "builder", "helpdesk"} <= slugs
    assert store.user_roles[demo_id("approver")] == {"approver"}
    assert store.conversations, "the example conversations are part of the demo tenant"
    assert store.durable_engine is None
