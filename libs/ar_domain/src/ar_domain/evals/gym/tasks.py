"""Load golden tool-choice tasks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class ArgRule:
    """One argument constraint. ``contains`` is a substring check on the value."""

    name: str
    contains: tuple[str, ...] = ()
    equals: str | None = None


@dataclass(frozen=True, slots=True)
class Expectation:
    """What a passing run must do. This is the scorecard, not the model."""

    tool: str
    args: tuple[ArgRule, ...]
    contains: tuple[str, ...]
    must_not_contain: tuple[str, ...]
    grounded: str
    terminal: str


@dataclass(frozen=True, slots=True)
class Task:
    """One golden instruction."""

    id: str
    title: str
    instruction: str
    attachments: tuple[str, ...]
    expect: Expectation

    def rendered(self, document_id: str) -> str:
        """Fill the library document id into the instruction and arg rules."""
        return self.instruction.replace("{document_id}", document_id)

    def bound(self, document_id: str) -> Task:
        """Return the task with ``{document_id}`` filled in expectations too."""
        rules = tuple(
            ArgRule(
                name=rule.name,
                contains=tuple(
                    part.replace("{document_id}", document_id) for part in rule.contains
                ),
                equals=None
                if rule.equals is None
                else rule.equals.replace("{document_id}", document_id),
            )
            for rule in self.expect.args
        )
        expect = Expectation(
            tool=self.expect.tool,
            args=rules,
            contains=self.expect.contains,
            must_not_contain=self.expect.must_not_contain,
            grounded=self.expect.grounded,
            terminal=self.expect.terminal,
        )
        return Task(
            id=self.id,
            title=self.title,
            instruction=self.rendered(document_id),
            attachments=self.attachments,
            expect=expect,
        )


def tasks_path() -> Path:
    """Repository fixture. Walks parents so an installed copy still finds it."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "docs" / "testing" / "eval-gym" / "tasks.yaml"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("docs/testing/eval-gym/tasks.yaml")


def load_tasks(path: Path | None = None) -> list[Task]:
    """Read the golden file. A missing field is an error, not a skipped task."""
    source = path or tasks_path()
    loaded = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("tasks.yaml must be a mapping")
    raw = loaded.get("tasks")
    if not isinstance(raw, list) or not raw:
        raise ValueError("tasks.yaml needs a tasks list")
    return [_task(item) for item in raw]


def _task(item: object) -> Task:
    if not isinstance(item, dict):
        raise TypeError("each task must be a mapping")
    expect = item.get("expect")
    if not isinstance(expect, dict):
        raise TypeError(f"{item.get('id')} needs expect")
    answer = expect.get("answer")
    answer_map = answer if isinstance(answer, dict) else {}
    grounded = str(answer_map.get("grounded") or "quote")
    if grounded not in {"quote", "approval", "not_found"}:
        raise ValueError(f"unknown grounded mode {grounded}")
    contains = _strings(answer_map.get("contains"))
    if grounded == "quote" and not contains:
        raise ValueError(f"{item.get('id')} quote grounding needs answer.contains")
    return Task(
        id=_text(item, "id"),
        title=_text(item, "title"),
        instruction=_text(item, "instruction").strip(),
        attachments=_strings(item.get("attachments")),
        expect=Expectation(
            tool=_text(expect, "tool"),
            args=_args(expect.get("args")),
            contains=contains,
            must_not_contain=_strings(answer_map.get("must_not_contain")),
            grounded=grounded,
            terminal=str(expect.get("terminal") or "completed"),
        ),
    )


def _args(raw: object) -> tuple[ArgRule, ...]:
    if not isinstance(raw, dict):
        return ()
    rules: list[ArgRule] = []
    for name, spec in raw.items():
        if isinstance(spec, str):
            rules.append(ArgRule(name=str(name), equals=spec))
            continue
        if not isinstance(spec, dict):
            raise TypeError(f"arg {name} must be a string or a mapping")
        equals = spec.get("equals")
        rules.append(
            ArgRule(
                name=str(name),
                contains=_strings(spec.get("contains")),
                equals=None if equals is None else str(equals),
            )
        )
    return tuple(rules)


def _strings(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(str(item) for item in raw)


def _text(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"task field {key} is required")
    return value
