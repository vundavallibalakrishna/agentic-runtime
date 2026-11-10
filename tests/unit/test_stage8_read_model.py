"""Stage 8 read model. Proof label: unit (in-process, no network, no model).

The contract case that uses Postgres is ``test_stage8_read_model_contract``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ar_common.settings import BaseServiceSettings, EnvName, get_settings, set_settings
from ar_domain.audit.read import verify_public_chain
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.readmodel.audit import chain_candidates
from ar_domain.readmodel.boot import MemoryStoreRefusedError, build_product_store
from ar_domain.readmodel.model import RepositoryReadModel
from ar_mcp_gateway.main import create_application
from ar_testing.demo_tenant import seed_demo_tenant

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_VERSIONS = _ROOT / "libs/ar_domain/src/ar_domain/migrations/versions"
_SECRET = SecretStr("unit-test-cursor-secret")


def _prod_settings() -> BaseServiceSettings:
    return BaseServiceSettings(
        _env_file=None,
        env=EnvName.PROD,
        cursor_secret=_SECRET,
    )


def test_production_boot_refuses_the_memory_double() -> None:
    previous = get_settings()
    set_settings(_prod_settings())
    try:
        with pytest.raises(MemoryStoreRefusedError):
            ChatService()
        store = build_product_store(
            _prod_settings(), allow_loopback=False, fake_models_allowed=False
        )
    finally:
        set_settings(previous)
    assert isinstance(store, RepositoryReadModel)
    assert not isinstance(store, ChatService)
    assert store.holds_tenant_state() is False
    other = build_product_store(_prod_settings(), allow_loopback=False)
    assert other is not store
    assert other.holds_tenant_state() is False


def test_dev_boot_keeps_the_memory_double() -> None:
    settings = BaseServiceSettings(_env_file=None, env=EnvName.DEV)
    store = build_product_store(settings, allow_loopback=True, fake_models_allowed=True)
    assert isinstance(store, ChatService)


def test_gateway_audit_joins_the_chain_the_verifier_checks() -> None:
    app = create_application()
    seed_demo_tenant(app.state.chat)
    store = app.state.chat
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "files.list"
    )
    server = store.tool_server_versions[version["tool_server_version_id"]]
    server["endpoint_url"] = "https://blocked.example/mcp"
    client = TestClient(app)
    called = client.post(
        "/internal/v1/tool-calls:execute",
        json={
            "tenantId": str(demo_id("tenant")),
            "userId": str(demo_id("admin")),
            "toolVersionId": str(version["id"]),
            "arguments": {},
            "modelCallId": "remote",
        },
    )
    assert called.status_code == 200, called.text
    chain = list(store.audit_chain)
    assert chain_candidates(store.audit_log)
    assert any(
        row.get("action") == "tool.denied" and row.get("detail", {}).get("via") == "gateway"
        for row in chain
    )
    report = verify_public_chain(chain)
    assert report["ok"] is True
    assert report["checked"] == len(chain)
    tampered = dict(chain[-1])
    tampered["action"] = "tool.called"
    broken = verify_public_chain([*chain[:-1], tampered])
    assert broken["ok"] is False


def test_single_alembic_head_is_stage5_revision() -> None:
    revisions: dict[str, str | None] = {}
    for path in _VERSIONS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        revision: str | None = None
        down: str | None = None
        for node in tree.body:
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if not isinstance(node.value, ast.Constant):
                continue
            if node.target.id == "revision" and isinstance(node.value.value, str):
                revision = node.value.value
            if node.target.id == "down_revision":
                down = node.value.value if isinstance(node.value.value, str) else None
        if revision is not None:
            revisions[revision] = down
    pointed = {item for item in revisions.values() if item}
    heads = sorted(rev for rev in revisions if rev not in pointed)
    assert heads == ["0038"]
