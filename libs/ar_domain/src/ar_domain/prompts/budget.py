"""Token estimates. Prefer an upstream tokenizer, then tiktoken, then a character estimate."""

import hashlib
from pathlib import Path


def estimate_tokens(text: str) -> int:
    """Count tokens. tiktoken is used when it is installed."""
    try:
        import tiktoken  # noqa: PLC0415
    except ImportError:
        return max(1, len(text) // 4) if text else 0
    encoder = tiktoken.get_encoding("o200k_base")
    return len(encoder.encode(text))


def truncate_history(
    history: list[dict[str, str]],
    *,
    budget: int,
    reserved: int,
) -> list[dict[str, str]]:
    """Drop the oldest history turns until the remainder fits. Blocks 1-5 stay."""
    kept = list(history)
    while kept and sum(estimate_tokens(item["content"]) for item in kept) + reserved > budget:
        kept.pop(0)
    return kept


def prompt_hash(messages: list[dict[str, str]]) -> str:
    """Stable hash stored on the model step. The prompt text is not logged."""
    payload = "\n".join(f"{item['role']}:{item['content']}" for item in messages)
    return hashlib.sha256(payload.encode()).hexdigest()


def read_prompt(name: str) -> str:
    """Load a versioned prompt file shipped with the runtime."""
    path = Path(__file__).resolve().parent / "text" / name
    return path.read_text(encoding="utf-8").strip()
