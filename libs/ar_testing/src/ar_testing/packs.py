"""Install a fixture pack without importing an industry package."""

from typing import Any, cast

from ar_domain.packs.registry import register_migrator


def install_fixture(store: Any, actor: Any) -> dict[str, object]:
    """Register the fixture schema and install its signed-optional manifest."""
    from ar_domain.agents.packs import PackService  # noqa: PLC0415

    def migrate(target: Any, who: Any, schema: str) -> None:
        del who
        from ar_domain.records.memory import bucket  # noqa: PLC0415

        bucket(target, "pack_migrations")[schema] = {"schema": schema, "upgraded": True}

    register_migrator("fixture_pack", migrate)
    manifest = {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {"id": "fixture", "version": "1.0.0", "name": "Fixture"},
        "spec": {
            "resources": [],
            "extension": {
                "schema": "fixture_pack",
                "permissions": ["fixture.records:read"],
                "auditActions": ["fixture.record.noted"],
                "configSchema": {"label": "Fixture"},
                "ui": {
                    "nav": [
                        {
                            "slot": "nav",
                            "href": "/ext/fixture",
                            "label": "Fixture",
                            "permission": "fixture.records:read",
                        }
                    ]
                },
            },
        },
    }
    return PackService(store).install(
        actor, cast("dict[str, object]", manifest), signature=None, key_id=None
    )
