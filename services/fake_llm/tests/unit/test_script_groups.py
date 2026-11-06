"""A script can quote what its pattern captured, safely inside a JSON answer."""

import orjson

from ar_fake_llm.scripts import ChatTurn, Script, select


def _turn(text: str, system: str = "") -> ChatTurn:
    return ChatTurn(last_user=text, system=system, last_tool_name=None, last_tool_result=None)


def test_a_script_quotes_a_captured_group_as_json_text() -> None:
    script = Script.model_validate(
        {
            "match": {"regex": r"(?i)remember that\s+([^.\n]+)"},
            "respond": {"text": '[{"content": "{{group:1}}"}]'},
        }
    )
    answer = select([script], _turn('Remember that the door code is  "A\\7".'))
    assert orjson.loads(answer.text or "") == [{"content": 'the door code is "A\\7"'}]


def test_a_group_the_pattern_does_not_have_renders_empty() -> None:
    script = Script.model_validate(
        {"match": {"regex": "tea"}, "respond": {"text": "[{{group:1}}] {{last_user}}"}}
    )
    assert select([script], _turn("more tea")).text == "[] more tea"


def test_a_script_without_a_pattern_keeps_the_placeholder_out_of_the_way() -> None:
    script = Script.model_validate({"match": {"contains": "tea"}, "respond": {"text": "ok"}})
    assert select([script], _turn("tea")).text == "ok"
