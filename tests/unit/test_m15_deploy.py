import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

from ar_common.settings import CATALOGUE_ENV

ROOT = Path(__file__).resolve().parents[2]


def load(relative: str, name: str) -> ModuleType:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _chain(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    previous = ""
    chained: list[dict[str, str]] = []
    for row in rows:
        body = f"{previous}|{row['action']}|{row['target_id']}"
        digest = hashlib.sha256(body.encode()).hexdigest()
        chained.append({**row, "hash": digest})
        previous = digest
    return chained


def test_catalogue_is_in_chart_values() -> None:
    text = (ROOT / "deploy/helm/agentic-runtime/values.yaml").read_text(encoding="utf-8")
    missing = sorted(name for name in CATALOGUE_ENV if name not in text)
    assert missing == []


def test_restore_dataset_meets_rpo() -> None:
    verify = load("scripts/dr/verify_restore.py", "verify_restore")
    report = verify.check_dataset(
        {
            "rows": {"tenants": 1, "document_chunks": 3},
            "wal_archive_timeout_s": 300,
            "audit": _chain(
                [
                    {"action": "tenant.created", "target_id": "dev"},
                    {"action": "user.created", "target_id": "admin"},
                ]
            ),
        },
        elapsed_s=2,
    )
    assert report["ok"] is True
    assert report["rpoSeconds"] <= 900


def test_export_and_reconcile() -> None:
    export = load("scripts/dr/export_tenant.py", "export_tenant")
    reconcile = load("scripts/dr/reconcile_temporal.py", "reconcile_temporal")
    exported = export.export_tenant(
        {
            "tables": {
                "tenants": [{"id": "t1"}, {"id": "t2"}],
                "users": [{"tenant_id": "t1", "email": "a@dev.local"}],
                "audit_events": [],
                "documents": [],
                "document_chunks": [{"tenant_id": "t2"}],
            }
        },
        "t1",
    )
    assert exported["tenants"] == [{"id": "t1"}]
    assert exported["users"][0]["email"] == "a@dev.local"
    assert exported["document_chunks"] == []
    assert reconcile.runs_to_terminate({"run-1"}, {"run-1", "run-2"}) == ["run-2"]


def test_release_dry_run(capsys) -> None:
    release = load("scripts/release.py", "release_mod")
    release.main(["--dry-run"])
    captured = capsys.readouterr()
    assert "release 1.0.0" in captured.out
    assert "dry-run" in captured.out


def test_locust_scenarios_are_present() -> None:
    locustfile = (ROOT / "tests/load/locustfile.py").read_text(encoding="utf-8")
    chat = (ROOT / "tests/load/scenarios/chat.py").read_text(encoding="utf-8")
    tools = (ROOT / "tests/load/scenarios/tools.py").read_text(encoding="utf-8")
    assert "ChatUser" in locustfile
    assert "class ChatUser" in chat
    assert "class ToolUser" in tools
    assert "sse" in chat
    assert "routines" in tools


def test_probe_stays_inside_platform_budgets() -> None:
    harness = load("tests/load/harness.py", "load_harness")
    report = harness.run_probe(requests=30)
    assert report["simple_get_p95_ms"] < harness.BUDGETS_MS["simple_get"]
    assert report["post_message_p95_ms"] < harness.BUDGETS_MS["post_message"]
