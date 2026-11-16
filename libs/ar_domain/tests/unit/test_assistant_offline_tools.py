"""The default assistant does not bind web tools. An editor adds them back."""

import importlib

from ar_domain.agents.logic import assistant_definition


def _migration() -> object:
    return importlib.import_module(
        "ar_domain.migrations.versions.20261115_0046_assistant_offline_tools"
    )


def _general(definition: dict[str, object]) -> list[str]:
    tools = definition["tools"]
    assert isinstance(tools, list)
    for grant in tools:
        if isinstance(grant, dict) and grant.get("server") == "general":
            include = grant["include"]
            assert isinstance(include, list)
            return [str(name) for name in include]
    return []


def test_the_default_assistant_has_no_web_tools() -> None:
    names = set(_general(assistant_definition()))
    assert {"fetch", "http", "search"}.isdisjoint(names)
    assert "code" in names
    assert "chart" in names


def test_the_migration_drops_web_tools_and_downgrade_restores_them() -> None:
    migration = _migration()
    current = assistant_definition()
    for grant in current["tools"]:  # type: ignore[union-attr]
        if isinstance(grant, dict) and grant.get("server") == "general":
            grant["include"] = ["code", "fetch", "http", "search", "chart"]
    stripped = migration._without(current)  # type: ignore[attr-defined]
    assert stripped is not None
    assert {"fetch", "http", "search"}.isdisjoint(set(_general(stripped)))
    restored = migration._with(stripped)  # type: ignore[attr-defined]
    assert {"fetch", "http", "search"} <= set(_general(restored))


def test_a_wildcard_general_grant_is_left_alone() -> None:
    migration = _migration()
    wide = {"tools": [{"server": "general", "version": "*", "include": ["*"]}]}
    assert migration._without(wide) is None  # type: ignore[attr-defined]
