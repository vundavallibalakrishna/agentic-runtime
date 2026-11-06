"""The code tool shows what a script computed (M38b-T08).

On the live tenant a script ended in ``totals.to_string()`` without printing it. The tool
returned only what had been printed, and the model made the totals up. The value of the
last expression is now shown, as a notebook shows it, and a command with no output says so.
"""

from __future__ import annotations

import uuid

from ar_domain.demo_ids import demo_id
from ar_domain.tools.general import dispatch_general, showing_last_value
from ar_testing.demo import demo_store


def _who() -> dict[str, object]:
    return {"_tenant_id": demo_id("tenant"), "_user_id": demo_id("admin"), "_run_id": uuid.uuid4()}


def _python(source: str) -> dict[str, object]:
    return dispatch_general(demo_store(), "code", {**_who(), "source": source})


def test_the_value_of_the_last_expression_is_shown() -> None:
    ran = _python("totals = {'east': 1042.5, 'north': 817.0}\ntotals")
    assert ran["is_error"] is False, ran["text"]
    assert "{'east': 1042.5, 'north': 817.0}" in str(ran["text"])


def test_a_string_is_shown_as_text_not_as_a_literal() -> None:
    ran = _python("rows = ['East 1042.5', 'North 817.0']\n'\\n'.join(rows)")
    assert "East 1042.5\nNorth 817.0" in str(ran["text"])


def test_printed_output_and_the_last_value_both_appear_in_order() -> None:
    ran = _python("print('columns ok')\nsum([1, 2, 3])")
    assert str(ran["structured"]["presentation"]["stdout"]) == "columns ok\n6\n"


def test_a_last_expression_with_no_value_shows_nothing_more() -> None:
    ran = _python("print('done')")
    assert str(ran["structured"]["presentation"]["stdout"]) == "done\n"


def test_a_command_that_prints_nothing_says_so() -> None:
    ran = _python("total = 6 * 7")
    assert ran["is_error"] is False
    assert str(ran["text"]) == "exit 0\nThe command printed nothing and wrote no file."


def test_only_the_last_statement_changes() -> None:
    assert showing_last_value("a = 1\nb = 2\n") == "a = 1\nb = 2\n"
    assert showing_last_value("") == ""
    assert showing_last_value("def broken(:\n") == "def broken(:\n", "Python reports the error"
    shown = showing_last_value("a = 1\n\na + 1  # the answer\n")
    assert shown.startswith("a = 1\n\n_ = (a + 1)\n")
    one_line = showing_last_value("a = 1; a")
    assert one_line.startswith("a = 1;\n_ = (a)\n")
    spread = showing_last_value("f = max\nf(\n    1,\n    2,\n)\n")
    assert spread.startswith("f = max\n_ = (f(\n    1,\n    2,\n))\n")


def test_an_error_keeps_the_scripts_own_line_number() -> None:
    ran = _python("a = 1\nb = 2\nmissing_name\n")
    assert ran["is_error"] is True
    assert "line 3" in str(ran["text"])
    assert "NameError" in str(ran["text"])
