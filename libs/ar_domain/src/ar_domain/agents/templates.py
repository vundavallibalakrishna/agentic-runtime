"""Starter definitions. Spec: docs/03-specs/05-agent-registry.md §3."""

from ar_domain.agents.logic import assistant_definition

TEMPLATES = ("blank", "assistant", "researcher", "analyst", "support")


def _copy(name: str, greeting: str, instructions: str, prompts: list[str]) -> dict[str, object]:
    definition = assistant_definition()
    definition["persona"] = {"display_name": name, "greeting": greeting}
    definition["instructions"] = instructions
    definition["starter_prompts"] = prompts
    definition["tools"] = []
    return definition


def template_definition(template: str, *, name: str) -> dict[str, object]:
    """Return a publishable definition for a template id."""
    if template == "researcher":
        return _copy(
            name,
            "Tell me what you want to understand.",
            "You research a question, separate what is known from what is uncertain, "
            "and answer in short sections with the sources you would want next.",
            ["What should I read first?", "List the open questions"],
        )
    if template == "analyst":
        return _copy(
            name,
            "Share the numbers or the decision you are weighing.",
            "You analyse the material the user provides. State the conclusion first, "
            "then the evidence, then what would change the conclusion.",
            ["Summarise the main change", "What is still unclear?"],
        )
    if template == "support":
        return _copy(
            name,
            "Tell me what you need help with.",
            "You help people complete a task. Ask one clarifying question when the "
            "request is ambiguous, then give the next step.",
            ["I need help with a request", "What information are you missing?"],
        )
    if template == "blank":
        return _copy(name, "", "Follow the user's instructions.", [])
    return _copy(
        name,
        "Hello. I can help with writing, summaries and questions.",
        "You are a helpful corporate assistant. Answer clearly and briefly.",
        ["Draft a short status update", "Explain this in simpler terms"],
    )


def helpdesk_definition() -> dict[str, object]:
    """Sample published agent seeded for the dev tenant."""
    return template_definition("support", name="Helpdesk")


def builder_definition() -> dict[str, object]:
    """Built-in agent that proposes definitions. It does not publish them."""
    definition = template_definition("blank", name="Builder")
    definition["instructions"] = (
        "You help a person create an agent from a plain-language request. "
        "Propose a persona, instructions, starter prompts and the tool slots they will need. "
        "Do not publish the agent. Leave a warning when a tool is not connected yet."
    )
    definition["starter_prompts"] = [
        "Create an agent that reviews vendor SOC 2 reports and flags gaps",
    ]
    definition["channels"] = {
        "web": True,
        "slack": False,
        "teams": False,
        "email": False,
        "api": False,
        "widget": False,
    }
    return definition
