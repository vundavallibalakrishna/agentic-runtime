"""Render recalled facts for the prompt. Spec: docs/03-specs/07-agent-runtime.md §4."""

from ar_common.wrapping import neutralise


def memory_block(facts: list[dict[str, object]]) -> str:
    """Wrap user-owned facts. Low-trust rows are labelled inside the block."""
    if not facts:
        return ""
    lines = ['<memory trust="user_data">']
    for fact in facts:
        content = neutralise(str(fact.get("content") or ""))
        trust = "low" if fact.get("trust_level") == "low" else "user_data"
        category = str(fact.get("category") or "fact")
        lines.append(
            f'<fact id="{fact.get("id")}" category="{category}" trust="{trust}">{content}</fact>'
        )
    lines.append("</memory>")
    return "\n".join(lines)
