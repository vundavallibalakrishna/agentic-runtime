"""Upgrade order in the Compose install."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_upgrade_runs_roles_then_schema_then_temporal() -> None:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "temporalio/server:1.32.1" in text
    assert "temporalio/admin-tools:1.32.1" in text
    assert "service_completed_successfully" in text
    assert "ar_domain.db.reconcile_roles" in text
    assert "ar_domain.db.schema_gate" in text
    reconcile = text.index('entrypoint: ["python", "-m", "ar_domain.db.reconcile_roles"]')
    migrate = text.index('entrypoint: ["python", "-m", "ar_domain.db.schema_gate"]')
    schema = text.index("image: temporalio/admin-tools:1.32.1")
    temporal = text.index("image: temporalio/server:1.32.1")
    assert reconcile < migrate < schema < temporal


def test_upgrade_script_recreates_one_shots() -> None:
    text = (ROOT / "scripts" / "compose_upgrade.sh").read_text(encoding="utf-8")
    assert "reconcile-roles" in text
    assert "migrate" in text
    assert "temporal-schema" in text
    assert "docker compose" in text
