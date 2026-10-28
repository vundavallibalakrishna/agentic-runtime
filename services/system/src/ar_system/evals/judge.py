"""Judge prompt loader. Spec: docs/08-quality/eval-strategy.md §4."""

from pathlib import Path


def judge_prompt() -> str:
    """Return the judge instructions shipped with the worker."""
    path = Path(__file__).resolve().parents[1] / "prompts" / "judge.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return (
        "Score the assistant reply against the rubric. "
        'Reply with JSON {"score": number, "reason": string}.'
    )
