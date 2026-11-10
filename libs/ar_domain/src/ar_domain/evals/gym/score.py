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
    expected_tool: str
    tool_selected: bool
    args_ok: bool
    answer_grounded: bool
    note: str

    @property
    def passed(self) -> bool:
        return self.tool_selected and self.args_ok and self.answer_grounded


@dataclass(frozen=True, slots=True)
class Report:
    """One gym run. ``dry-run`` is proof ``unit``. ``live`` names the model and the date."""

    mode: str
    scores: tuple[TaskScore, ...]
    model_id: str = ""
    reported_on: str = ""

    def __post_init__(self) -> None:
        if self.mode not in {"dry-run", "live"}:
            raise ValueError("an eval artifact is dry-run or live")
        if self.mode == "live" and (not self.model_id.strip() or not self.reported_on.strip()):
            raise ValueError("a live report names the model id and the date")
        if self.mode != "live" and (self.model_id or self.reported_on):
            raise ValueError("a dry-run report does not name a model")

    @property
    def proof(self) -> str:
        return "live" if self.mode == "live" else "unit"

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


def _chain_matched(observed: list[str], chain: tuple[str, ...]) -> bool:
    """True when every tool in ``chain`` appears in ``observed`` in that order."""
    index = 0
    for name in observed:
        if index < len(chain) and name == chain[index]:
            index += 1
    return index == len(chain)


def tool_breakdown(report: Report) -> list[tuple[str, int, int]]:
    """Per expected tool: (tool, tasks that selected it, total tasks expecting it)."""
    totals: dict[str, int] = {}
    hits: dict[str, int] = {}
    for row in report.scores:
        tool = row.expected_tool
        totals[tool] = totals.get(tool, 0) + 1
        hits[tool] = hits.get(tool, 0) + (1 if row.tool_selected else 0)
    return [(tool, hits[tool], totals[tool]) for tool in sorted(totals)]


def score_observation(
    task: Task,
    *,
    calls: list[ObservedCall],
    answer: str,
    status: str,
) -> TaskScore:
    """Score tool selection, arguments, and whether the answer follows the tool."""
    matched = [call for call in calls if canonical_tool(call.name) == task.expect.tool]
    if task.expect.chain:
        tool_ok = _chain_matched([canonical_tool(call.name) for call in calls], task.expect.chain)
    else:
        tool_ok = bool(matched)
    args_ok = bool(matched) and all(
        _arg_ok(rule, matched[0].arguments) for rule in task.expect.args
    )
    grounded = _grounded(task, calls, answer, status)
    note = _note(task, calls, answer, status, tool_ok=tool_ok, args_ok=args_ok, grounded=grounded)
    return TaskScore(
        task_id=task.id,
        title=task.title,
        expected_tool=" → ".join(task.expect.chain) if task.expect.chain else task.expect.tool,
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
        f"Proof: `{report.proof}`.",
        _proof_sentence(report),
        "",
        "Each task passes when the agent loop selected the expected tool, the arguments",
        "matched, and the final answer is grounded in the tool result. `not_found` passes",
        "only when the tool said the passage was missing and the answer does not invent it.",
        "An approval task passes when the run is waiting and the answer does not claim success.",
        "",
        "The dry-run mode replays a scripted model through the real agent loop and does not",
        "call a paid provider. A live run is a separate file. It names the model id and the date.",
        "See `docs/testing/m33c-checklist.md`.",
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
            "## Per-tool selection",
            "",
            "How often the model chose the expected tool (or chain), by tool.",
            "",
            "| Tool | Selected | Rate |",
            "|---|---|---|",
        ]
    )
    for tool, hit, total in tool_breakdown(report):
        rate = round(100 * hit / total) if total else 0
        lines.append(f"| `{tool}` | {hit}/{total} | {rate}% |")
    lines.append("")
    return "\n".join(lines)


def _proof_sentence(report: Report) -> str:
    if report.proof == "live":
        return f"Model: `{report.model_id}`. Date: `{report.reported_on}`."
    return "A dry-run is unit. It is not a live result, and it names no model."


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
    tool_says = any(
        token in blob for token in ("not_found", "not_supported", "not_judged", "not found")
    )
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
