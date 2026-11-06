"""The tenant's masking of personal data is read and changed through the API (M38b-T09)."""

import importlib.util
import uuid
from pathlib import Path


def _surface():
    path = Path(__file__).resolve().parent / "test_api_surface.py"
    spec = importlib.util.spec_from_file_location("m38b_api_surface", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _masked(view: dict[str, object]) -> set[str]:
    return {row["name"] for row in view["kinds"] if row["masked"]}


def test_a_tenant_reads_and_changes_what_is_masked() -> None:
    surface = _surface()
    client = surface._app(surface._principal(uuid.uuid4(), uuid.uuid4()))

    start = client.get("/api/v1/tenant/masking")
    assert start.status_code == 200, start.text
    view = start.json()
    assert set(view) == {"enabled", "usesDefault", "minScore", "defaultMinScore", "kinds"}
    assert view["enabled"] is True
    assert view["usesDefault"] is True
    assert view["minScore"] == view["defaultMinScore"]
    assert set(view["kinds"][0]) == {"name", "source", "masked", "default"}
    assert {"email_address", "credit_card"} <= _masked(view)
    assert "person" not in _masked(view), "a name is not masked unless the tenant asks"

    saved = client.patch(
        "/api/v1/tenant",
        json={
            "settings": {
                "privacy": {"redactionEntities": ["person", "email_address"]},
            }
        },
    )
    assert saved.status_code == 200, saved.text
    scored = client.patch(
        "/api/v1/tenant", json={"settings": {"privacy": {"redactionMinScore": 0.8}}}
    )
    assert scored.status_code == 200, scored.text
    chosen = client.get("/api/v1/tenant/masking").json()
    assert chosen["usesDefault"] is False
    assert chosen["minScore"] == 0.8
    assert _masked(chosen) == {"person", "email_address"}

    reset = client.patch(
        "/api/v1/tenant",
        json={"settings": {"privacy": {"redactionEntities": None, "redactionMinScore": None}}},
    )
    assert reset.status_code == 200, reset.text
    assert client.get("/api/v1/tenant/masking").json() == view


def test_an_unknown_kind_is_refused_and_named() -> None:
    surface = _surface()
    client = surface._app(surface._principal(uuid.uuid4(), uuid.uuid4()))
    wrong = client.patch(
        "/api/v1/tenant", json={"settings": {"privacy": {"redactionEntities": ["shoe_size"]}}}
    )
    assert wrong.status_code == 422
    assert "shoe_size" in wrong.json()["detail"]
    high = client.patch("/api/v1/tenant", json={"settings": {"privacy": {"redactionMinScore": 2}}})
    assert high.status_code == 422


def test_reading_needs_the_tenant_permission_and_another_tenant_keeps_its_own() -> None:
    surface = _surface()
    nobody = surface._app(
        surface._principal(uuid.uuid4(), uuid.uuid4(), permissions=frozenset({"chat:use"}))
    )
    assert nobody.get("/api/v1/tenant/masking").status_code == 403

    first = surface._app(surface._principal(uuid.uuid4(), uuid.uuid4()))
    second = surface._app(surface._principal(uuid.uuid4(), uuid.uuid4()))
    changed = first.patch(
        "/api/v1/tenant", json={"settings": {"privacy": {"redactionEntities": []}}}
    )
    assert changed.status_code == 200, changed.text
    assert _masked(first.get("/api/v1/tenant/masking").json()) == set()
    assert "email_address" in _masked(second.get("/api/v1/tenant/masking").json())
