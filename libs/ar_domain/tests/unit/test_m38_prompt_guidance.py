"""Tool guidance and the output schema reach the model on every path (M38-T05, review A7).

The guidance was appended only when a run had no prepared prompt. A chat turn always has
one, so on the path people use the model was never told to compute rather than guess, to
read an error and try again, or to answer in the agent's output schema. On the live tenant
it added a column itself and said 75 where the file says 80.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from ar_domain.demo_ids import demo_id
from ar_domain.memory.session import prepare_prompt
from ar_domain.prompts.assembler import build_prompt, output_block, uses_tools
from ar_domain.prompts.budget import read_prompt
from ar_domain.workspace.turn import opening_messages
from ar_testing.demo import demo_store

TENANT = demo_id("tenant")
USER = demo_id("admin")
GUIDANCE = read_prompt("tool_use.md")
SCHEMA = {"type": "object", "properties": {"total": {"type": "number"}}, "required": ["total"]}
SOURCE = Path(__file__).resolve().parents[2] / "src" / "ar_domain"


def _system(definition: dict[str, object]) -> str:
    return build_prompt({"definition": definition, "user_text": "Hi"}).messages[0]["content"]


def test_an_agent_with_tools_is_told_how_to_use_them() -> None:
    system = _system({"instructions": "Be brief.", "tools": [{"server": "general"}]})
    assert GUIDANCE in system
    # The rules the live run showed were missing.
    assert "run code or a query and report what it returned" in system
    assert "Never fill a gap with a likely value" in system
    assert "call the tool again with corrected arguments" in system
    # Platform rules first, then tool guidance, then the agent's own instructions.
    assert (
        system.index(read_prompt("platform.md"))
        < system.index(GUIDANCE)
        < system.index("Be brief.")
    )


def test_an_agent_that_can_only_call_other_agents_is_told_too() -> None:
    assert uses_tools({"subagents": {"allowed": ["researcher"]}}) is True
    assert uses_tools({"subagents": {"allow_self_clone": True}}) is True
    assert GUIDANCE in _system({"subagents": {"allowed": ["researcher"]}})


def test_an_agent_with_nothing_to_call_is_not_given_tool_rules() -> None:
    for definition in ({}, {"tools": []}, {"subagents": {"allowed": []}}, {"subagents": "none"}):
        assert uses_tools(definition) is False
        assert GUIDANCE not in _system({"instructions": "Be brief.", **definition})


def test_the_output_schema_is_part_of_the_system_prompt() -> None:
    definition = {"instructions": "Add it up.", "output": {"json_schema": SCHEMA}}
    system = _system(definition)
    assert "Return only JSON matching this schema:" in system
    assert '"required":["total"]' in system
    assert system.index("Add it up.") < system.index("Return only JSON")
    assert output_block({"instructions": "No schema."}) == ""
    assert "Return only JSON" not in _system({"instructions": "No schema."})


def test_a_chat_turn_carries_the_guidance_and_the_schema() -> None:
    """The prepared prompt of a real turn, which is what the model is sent."""
    store = demo_store()
    conversation = store.create_conversation(TENANT, USER, None)
    posted = store.post_message(
        TENANT, USER, uuid.UUID(str(conversation["id"])), "Total the units", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    row = store.conversations[run["conversation_id"]]
    version = store.versions[store.agents[row["agent_id"]]["published_version_id"]]
    definition = {**version["definition"], "output": {"json_schema": SCHEMA}}
    assert uses_tools(definition), "the default assistant has tools"

    prepare_prompt(store, run, row, definition, "Total the units")

    system = run["prompt_messages"][0]["content"]
    assert GUIDANCE in system
    assert "Return only JSON matching this schema:" in system
    assert opening_messages(run, definition, "Total the units") == run["prompt_messages"]


def test_a_run_without_a_prepared_prompt_gets_the_same_system_blocks() -> None:
    """A child run another agent called starts here."""
    definition = {
        "instructions": "Research the question.",
        "tools": [{"server": "general"}],
        "output": {"json_schema": SCHEMA},
    }
    opened = opening_messages({"orchestration_child": True}, definition, "Find the total")
    assert [item["role"] for item in opened] == ["system", "user"]
    system = opened[0]["content"]
    assert read_prompt("platform.md") in system
    assert GUIDANCE in system
    assert "Research the question." in system
    assert "Return only JSON matching this schema:" in system
    assert opened[1]["content"] == "Find the total"
    assert system == _system_for(definition, "Find the total")


def _system_for(definition: dict[str, object], text: str) -> str:
    return build_prompt({"definition": definition, "user_text": text}).messages[0]["content"]


def test_the_guidance_names_no_tool_and_lives_in_one_file() -> None:
    """A tool's own hints belong in its description, where an agent without it never reads them."""
    for name in ("documents.", "general.", "DuckDB", "sandbox.", "browser."):
        assert name not in GUIDANCE
    loop = (SOURCE / "tools" / "agent_loop.py").read_text(encoding="utf-8")
    assert "_GUIDE" not in loop
    assert "Return only JSON" not in loop
