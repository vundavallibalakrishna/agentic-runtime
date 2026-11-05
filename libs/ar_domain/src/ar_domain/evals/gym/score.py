"""Score one observed run. The model is not consulted here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ar_domain.evals.gym.tasks import ArgRule, Task


@dataclass(frozen=True, slots=True)
class ObservedCall:
    """One tool call the agent loop actually made."""

    name: str
    arguments: dict[str, object]
    result_text: str
    status: str


@dataclass(frozen=True, slots=True)
class TaskScore:
    """Three gates. A task passes only when all three are true."""

    task_id: str
    title: str
    tool_selected: bool
    args_ok: bool
    answer_grounded: bool
    note: str

    @property
    def passed(self) -> bool:
        return self.tool_selected and self.args_ok and self.answer_grounded


@dataclass(frozen=True, slots=True)
class Report:
    """One gym run."""

    mode: str
    scores: tuple[TaskScore, ...]

    @property
    def total(self) -> int:
        return len(self.scores)

    @property
    def passed_count(self) -> int:
        return sum(1 for row in self.scores if row.passed)

    @property
    def percent(self) -> int:
        if not self.scores:
            return 0
        return round(100 * self.passed_count / self.total)


def canonical_tool(name: str) -> str:
    """OpenAI names use a double underscore. The catalogue uses a dot."""
    return name.replace("__", ".")


def score_observation(
    task: Task,
    *,
    calls: list[ObservedCall],
    answer: str,
    status: str,
) -> TaskScore:
    """Score tool selection, arguments, and whether the answer follows the tool."""
    matched = [call for call in calls if canonical_tool(call.name) == task.expect.tool]
    tool_ok = bool(matched)
    args_ok = tool_ok and all(_arg_ok(rule, matched[0].arguments) for rule in task.expect.args)
    grounded = _grounded(task, calls, answer, status)
    note = _note(task, calls, answer, status, tool_ok=tool_ok, args_ok=args_ok, grounded=grounded)
    return TaskScore(
        task_id=task.id,
        title=task.title,
        tool_selected=tool_ok,
        args_ok=args_ok,
        answer_grounded=grounded,
        note=note,
    )


def render_scorecard(report: Report) -> str:
    """Markdown table. Stable for the dry-run so CI can keep the file in git."""
    lines = [
        "# M33c tool-choice scorecard",
        "",
        f"Mode: `{report.mode}`.",
        "",
        "Each task passes when the agent loop selected the expected tool, the arguments",
        "matched, and the final answer is grounded in the tool result. `not_found` passes",
        "only when the tool said the passage was missing and the answer does not invent it.",
        "An approval task passes when the run is waiting and the answer does not claim success.",
        "",
        "The dry-run mode replays a scripted model through the real agent loop and does not",
        "call a paid provider. A live Qwen3-32B run is a separate file. See",
        "`docs/testing/m33c-checklist.md`.",
        "",
        "| Task | Tool | Args | Grounded | Pass | Note |",
        "|---|---|---|---|---|---|",
    ]
    lines.extend(_row(row) for row in report.scores)
    lines.extend(
        [
            "",
            f"Aggregate: {report.passed_count}/{report.total} ({report.percent}%).",
            "",
        ]
    )
    return "\n".join(lines)


def _arg_ok(rule: ArgRule, arguments: dict[str, object]) -> bool:
    value = arguments.get(rule.name)
    if rule.equals is not None and str(value) != rule.equals:
        return False
    rendered = _flatten(value)
    return all(part in rendered for part in rule.contains)


def _flatten(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_flatten(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return "" if value is None else str(value)


def _grounded(task: Task, calls: list[ObservedCall], answer: str, status: str) -> bool:
    mode = task.expect.grounded
    if mode == "approval":
        return _approval_grounded(task, answer, status)
    if mode == "not_found":
        return _not_found_grounded(task, calls, answer, status)
    return _quote_grounded(task, calls, answer, status)


def _approval_grounded(task: Task, answer: str, status: str) -> bool:
    if status != task.expect.terminal:
        return False
    lowered = answer.lower()
    if "http 200" in lowered or "succeeded" in lowered:
        return False
    return all(banned.lower() not in lowered for banned in task.expect.must_not_contain)


def _not_found_grounded(task: Task, calls: list[ObservedCall], answer: str, status: str) -> bool:
    if status != task.expect.terminal:
        return False
    blob = _results(calls).lower()
    lowered = answer.lower()
    tool_says = "not_found" in blob or "not found" in blob
    answer_says = "not_found" in lowered or "not found" in lowered or "does not contain" in lowered
    clean = all(banned.lower() not in lowered for banned in task.expect.must_not_contain)
    return tool_says and answer_says and clean


def _quote_grounded(task: Task, calls: list[ObservedCall], answer: str, status: str) -> bool:
    if status != task.expect.terminal:
        return False
    blob = _results(calls)
    if any(banned.lower() in answer.lower() for banned in task.expect.must_not_contain):
        return False
    return all(part in answer and part in blob for part in task.expect.contains)


def _results(calls: list[ObservedCall]) -> str:
    return "\n".join(call.result_text for call in calls)


def _note(
    task: Task,
    calls: list[ObservedCall],
    answer: str,
    status: str,
    *,
    tool_ok: bool,
    args_ok: bool,
    grounded: bool,
) -> str:
    if tool_ok and args_ok and grounded:
        if task.expect.grounded == "approval":
            return "waiting_approval"
        if task.expect.grounded == "not_found":
            return "not_found"
        return ", ".join(task.expect.contains)
    called = ", ".join(canonical_tool(call.name) for call in calls) or "none"
    excerpt = " ".join(answer.split())[:80]
    return f"called {called}; status {status}; answer {excerpt}"


def _row(row: TaskScore) -> str:
    return "| {task} | {tool} | {args} | {grounded} | {passed} | {note} |".format(
        task=row.task_id,
        tool=_mark(ok=row.tool_selected),
        args=_mark(ok=row.args_ok),
        grounded=_mark(ok=row.answer_grounded),
        passed=_mark(ok=row.passed),
        note=row.note.replace("|", "/"),
    )


def _mark(*, ok: bool) -> str:
    return "pass" if ok else "fail"
