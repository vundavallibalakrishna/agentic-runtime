"""Eval-run tool policy. W2 and W3 are never executed.

Spec: docs/03-specs/18-observability-eval.md §4.4.
"""

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def prepare(store: Any, request: dict[str, object]) -> dict[str, object] | None:
    """Return a mock or a denial, or None when the call may execute."""
    run = _run(store, request)
    if run is None:
        return None
    context = run.get("eval_context")
    if not isinstance(context, dict):
        return None
    qualified = str(request.get("qualified_name") or _qualified(store, request))
    raw_mocks = context.get("tool_mocks")
    mocks = raw_mocks if isinstance(raw_mocks, list) else []
    for mock in mocks:
        if (
            isinstance(mock, dict)
            and str(mock.get("tool") or "") == qualified
            and _matches(mock, request)
        ):
            _count(store, "mocked")
            return _mock_result(mock)
    if context.get("mock_all_tools") is True:
        _count(store, "mocked")
        return _denied("eval_mock_required", "eval runs require a tool mock")
    if _risk(store, request) in {"W2", "W3"}:
        _count(store, "blocked_writes")
        return _denied("eval_write_blocked", "eval runs do not execute writes")
    return None


def counter(store: Any, name: str) -> int:
    """Gateway counter for tests. Real writes are not incremented."""
    gateway = getattr(store, "eval_gateway", None)
    raw = gateway.get(name, 0) if isinstance(gateway, dict) else 0
    return raw if isinstance(raw, int) else 0


def _run(store: Any, request: dict[str, object]) -> dict[str, object] | None:
    run_id = request.get("run_id")
    if not isinstance(run_id, uuid.UUID):
        return None
    run = store.runs.get(run_id)
    if not isinstance(run, dict):
        return None
    if run.get("trigger") != "eval" and not run.get("eval_context"):
        return None
    return run


def _qualified(store: Any, request: dict[str, object]) -> str:
    version_id = request.get("tool_version_id")
    version = store.tool_versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    if isinstance(version, dict):
        return str(version.get("qualified_name") or "")
    return ""


def _risk(store: Any, request: dict[str, object]) -> str:
    explicit = str(request.get("risk_class") or "")
    if explicit:
        return explicit
    version_id = request.get("tool_version_id")
    version = store.tool_versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    if isinstance(version, dict):
        return str(version.get("risk_class") or "")
    return ""


def _matches(mock: dict[str, object], request: dict[str, object]) -> bool:
    expected = mock.get("match_args")
    if not isinstance(expected, dict):
        return True
    arguments = request.get("arguments")
    if not isinstance(arguments, dict):
        return False
    return all(arguments.get(str(key)) == value for key, value in expected.items())


def _mock_result(mock: dict[str, object]) -> dict[str, object]:
    error = mock.get("error")
    if isinstance(error, dict):
        return {
            "status": "failed",
            "is_error": True,
            "text": str(error.get("message") or ""),
            "error": {
                "code": str(error.get("code") or "mock_error"),
                "message": str(error.get("message") or ""),
            },
        }
    result = mock.get("result") if isinstance(mock.get("result"), dict) else {}
    text = str(result.get("text") or "") if isinstance(result, dict) else ""
    return {"status": "completed", "is_error": False, "text": text, "structured": result}


def _denied(code: str, message: str) -> dict[str, object]:
    return {
        "status": "failed",
        "is_error": True,
        "text": message,
        "error": {"code": code, "message": message},
    }


def _count(store: Any, name: str) -> None:
    gateway = getattr(store, "eval_gateway", None)
    if not isinstance(gateway, dict):
        gateway = {}
        store.eval_gateway = gateway
    current = gateway.get(name, 0)
    gateway[name] = (current if isinstance(current, int) else 0) + 1
