"""A product store starts with no tenant. Only test setup builds the demo tenant.

Task: M38b-T04c.
"""

import re
from pathlib import Path

from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_testing.demo import demo_store

ROOT = Path(__file__).resolve().parents[4]

# The eval gym and the eval command are eval tooling that work on the demo tenant on
# purpose. They move out of the product with M38b-T04d and M42.
_EVAL_TOOLING = {
    "libs/ar_domain/src/ar_domain/evals/gym/world.py",
    "services/system/src/ar_system/evals/cli.py",
}


def test_a_new_store_holds_no_tenant() -> None:
    store = ChatService()
    for bucket in (
        "agents",
        "versions",
        "conversations",
        "tenant_settings",
        "user_roles",
        "display_names",
        "review_queues",
        "eval_suites",
        "credential_grants",
        "data_connections",
        # No model provider, model or alias either: the admin adds those in the product.
        "providers",
        "models",
        "aliases",
    ):
        assert getattr(store, bucket) == {}, bucket
    assert store.demo_tenant_seeded is False
    # The built-in tool catalogue belongs to no tenant, so it is there from the start.
    assert store.tool_servers
    assert {row.get("tenant_id") for row in store.tool_servers.values()} == {None}
    slugs = {str(row["slug"]) for row in store.tool_servers.values()}
    assert not slugs & {"tickets", "petstore", "warehouse", "web"}


def test_the_test_library_builds_the_demo_tenant() -> None:
    store = demo_store(allow_loopback=True)
    assert store.allow_loopback is True
    slugs = {str(row["slug"]) for row in store.agents.values()}
    assert {"assistant", "builder", "helpdesk", "desk", "revenue-analyst"} <= slugs
    assert store.user_roles[demo_id("approver")] == {"approver"}
    assert "tickets" in {str(row["slug"]) for row in store.tool_servers.values()}
    # The demo's scripted chat provider, the stand-in providers for embeddings and for
    # deciding what to remember, and the aliases that point at them are test data too.
    assert [row["name"] for row in store.providers.values()] == [
        "fake-llm",
        "stand-in-embeddings",
        "stand-in-memory",
    ]
    assert {row["alias"] for row in store.aliases.values()} == {
        "reasoning",
        "fast",
        "vision",
        "embed",
        "rerank",
    }


def test_no_product_code_builds_the_demo_tenant() -> None:
    """Strict rule 3: a running product holds no built-in tenant."""
    call = re.compile(r"\.(seed_demo_tenant|seed_showcase|seed_demo)\(")
    callers: set[str] = set()
    for top in ("libs", "services", "connectors"):
        for path in (ROOT / top).glob("*/src/**/*.py"):
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith("libs/ar_testing/"):
                continue
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if call.search(line) and "self." not in line:
                    callers.add(relative)
    assert callers == _EVAL_TOOLING
