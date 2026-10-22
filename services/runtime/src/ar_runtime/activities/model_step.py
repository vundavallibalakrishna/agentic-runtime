"""Model step placeholder. The dev API still calls fake-llm in process (OQ-31)."""


def model_step(user_text: str) -> dict[str, object]:
    """Return the text the model asked to run. Tool parsing stays in the driver."""
    return {"text": user_text, "tool_calls": []}
