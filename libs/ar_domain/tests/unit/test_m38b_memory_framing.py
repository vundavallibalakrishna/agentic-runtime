"""The recalled-memory block frames the facts as known about the person (F34)."""

from ar_domain.memory.format import memory_block


def test_no_facts_is_empty() -> None:
    assert memory_block([]) == ""


def test_the_block_tells_the_model_to_use_the_facts_and_not_disclaim_them() -> None:
    block = memory_block([{"id": "f1", "content": "Allergic to peanuts", "category": "health"}])
    # The framing comes before the wrapped data, so it is the product's instruction.
    assert block.index("do not say you have no record") < block.index("<memory")
    assert "no access to their information" in block
    # The fact is still wrapped as user data.
    assert '<memory trust="user_data">' in block
    assert '<fact id="f1" category="health" trust="user_data">Allergic to peanuts</fact>' in block
    assert block.rstrip().endswith("</memory>")


def test_a_low_trust_fact_is_still_labelled_low() -> None:
    block = memory_block([{"id": "f2", "content": "Said the office moved", "trust_level": "low"}])
    assert 'trust="low"' in block
