"""Model step placeholder. The dev API still calls fake-llm in process (OQ-31)."""

from ar_common.telemetry import record_model_call


def model_step(user_text: str) -> dict[str, object]:
    """Return the text the model asked to run. Tool parsing stays in the driver."""
    record_model_call(model="fake", tokens_in=len(user_text), tokens_out=len(user_text))
    return {"text": user_text, "tool_calls": []}
