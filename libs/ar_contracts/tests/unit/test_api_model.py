"""Public JSON uses camelCase aliases. Python attributes stay snake_case."""

from ar_contracts.budget import RunUsage
from ar_contracts.messages import FilePart


def test_serialize_by_alias() -> None:
    usage = RunUsage(tokens_in=1, tokens_out=2)
    dumped = usage.model_dump()
    assert "tokensIn" in dumped
    assert "tokens_in" not in dumped
    assert dumped["tokensIn"] == 1


def test_populate_by_name_and_alias() -> None:
    by_python = FilePart.model_validate(
        {
            "type": "file",
            "file_id": "00000000-0000-7000-8000-000000000001",
            "name": "a",
            "mime_type": "text/plain",
        }
    )
    by_alias = FilePart.model_validate(
        {
            "type": "file",
            "fileId": "00000000-0000-7000-8000-000000000001",
            "name": "a",
            "mimeType": "text/plain",
        }
    )
    assert by_python.file_id == by_alias.file_id
    assert by_python.model_dump()["mimeType"] == "text/plain"


def test_json_schema_properties_are_camel_case() -> None:
    schema = RunUsage.model_json_schema(by_alias=True)
    assert "tokensIn" in schema["properties"]
    assert "tokens_in" not in schema["properties"]
