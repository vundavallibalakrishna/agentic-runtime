"""The developer notes and the API are checked against each other."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _check() -> object:
    spec = importlib.util.spec_from_file_location(
        "check_developer_notes", ROOT / "scripts" / "check_developer_notes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_notes_name_only_calls_that_exist_and_every_call_an_integrator_uses() -> None:
    assert _check().main() == 0  # type: ignore[attr-defined]


def test_two_spellings_of_one_call_compare_equal() -> None:
    shape = _check().shape  # type: ignore[attr-defined]
    contract = shape("/v1/agents/{slug}/conversations/{conversation_id}/messages")
    assert shape("/v1/agents/assistant/conversations/$CONVERSATION_ID/messages") == contract
    assert shape("/v1/agents/{{AGENT_SLUG}}/conversations/<id>/messages?x=1") == contract
    assert shape("/v1/agents/helpdesk:run") == shape("/v1/agents/{slug}:run")
    assert shape("/api/v1/files:upload") != shape("/api/v1/files:limits")


def test_a_note_that_names_a_call_the_api_lacks_is_reported(tmp_path: Path) -> None:
    check = _check()
    (tmp_path / "note.md").write_text("Call `POST /api/v1/no-such-thing` first.\n")
    check.NOTES = tmp_path  # type: ignore[attr-defined]
    assert check.main() == 1  # type: ignore[attr-defined]
