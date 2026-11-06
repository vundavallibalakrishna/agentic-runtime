"""The browser tests' API harness owns the demo tenant and the test sign-in.

Tasks: M38b-T04b, M38b-T05a.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from ar_api.main import create_application
from ar_domain.demo_ids import demo_id

HARNESS = Path(__file__).resolve().parents[1] / "support" / "e2e_server.py"


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    # The harness says "no database" through the environment; undo that after the test.
    monkeypatch.setenv("AR_DURABLE_STATE", "postgres")
    spec = importlib.util.spec_from_file_location("e2e_server", HARNESS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_harness_serves_the_product_app_over_the_demo_tenant(
    harness: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    served: dict[str, object] = {}

    def run(app: object, **options: object) -> None:
        served["app"] = app
        served.update(options)

    monkeypatch.setenv("AR_PORT", "18999")
    monkeypatch.setattr(harness.uvicorn, "run", run)

    harness.main()

    store = served["app"].product.state.chat  # type: ignore[attr-defined]
    assert served["port"] == 18999
    assert served["host"] == "127.0.0.1"
    slugs = {str(row["slug"]) for row in store.agents.values()}
    assert {"assistant", "builder", "helpdesk"} <= slugs
    assert store.user_roles[demo_id("approver")] == {"approver"}
    assert store.conversations, "the example conversations are part of the demo tenant"
    assert store.durable_engine is None


async def test_the_test_sign_in_is_in_the_harness_and_not_in_the_product(
    harness: ModuleType,
) -> None:
    path = harness.SIGN_IN_PATH
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=harness.build()), base_url="http://localhost:3000"
    ) as browser:
        signed_in = await browser.get(path, params={"email": "Approver@dev.local"})
        assert signed_in.status_code == 303
        assert signed_in.headers["location"] == "/chat"
        session = await browser.get("/api/v1/auth/session")
        assert session.status_code == 200
        assert session.json()["user"]["email"] == "approver@dev.local"
        assert session.json()["roles"] == ["approver"]
        posted = await browser.post(path, json={"email": "member@dev.local"})
        assert posted.status_code == 303
        stranger = await browser.get(path, params={"email": "ada@acme.example"})
        assert stranger.status_code == 404
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_application()), base_url="http://localhost:3000"
    ) as product:
        refused = await product.get(path, params={"email": "approver@dev.local"})
        assert refused.status_code in {401, 404}
        assert "set-cookie" not in refused.headers
