"""Run golden tasks through the agent loop and score them."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from ar_domain.evals.gym.live import install_live, live_settings
from ar_domain.evals.gym.policy import DryRunCompleter
from ar_domain.evals.gym.score import ObservedCall, Report, TaskScore, score_observation
from ar_domain.evals.gym.tasks import Task, load_tasks
from ar_domain.evals.gym.world import GymWorld, build_world

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ar_domain.chat.service import ChatService


async def run_suite_async(
    *,
    live: bool = False,
    environ: Mapping[str, str] | None = None,
    tasks: list[Task] | None = None,
) -> Report:
    """Score every golden task. ``live`` uses the cert key. Otherwise the scripted model runs."""
    mode = "live" if live else "dry-run"
    live_plan: tuple[str, str, str] | None = None
    if live:
        live_plan = live_settings(environ)
    world = build_world()
    if live_plan is not None:
        key, url, model = live_plan
        install_live(world.store, world.tenant_id, key=key, base_url=url, model=model)
    else:
        _install_dry_run(world.store)
    chosen = tasks if tasks is not None else load_tasks()
    scores: list[TaskScore] = []
    for task in chosen:
        bound = task.bound(world.document_id)
        scores.append(await _run_task(world, bound))
    return Report(mode=mode, scores=tuple(scores))


def run_suite(
    *,
    live: bool = False,
    environ: Mapping[str, str] | None = None,
    tasks: list[Task] | None = None,
) -> Report:
    """Synchronous wrapper used by the CLI and the unit test."""
    return asyncio.run(run_suite_async(live=live, environ=environ, tasks=tasks))


async def _run_task(world: GymWorld, task: Task) -> TaskScore:
    store = world.store
    conversation = store.create_conversation(
        world.tenant_id, world.user_id, world.agent_id, model_alias="reasoning"
    )
    attachments = [world.files[name] for name in task.attachments if name in world.files]
    posted = store.post_message(
        world.tenant_id,
        world.user_id,
        uuid.UUID(str(conversation["id"])),
        task.instruction,
        attachment_ids=attachments,
        schedule=False,
    )
    run_row = posted.get("run")
    if not isinstance(run_row, dict):
        raise TypeError("post_message did not return a run")
    run_id = uuid.UUID(str(run_row["id"]))
    await store.generate(run_id, task.instruction, _names(store, attachments))
    run = store.runs[run_id]
    assistant_id = run.get("assistant_message_id")
    assistant = store.messages.get(uuid.UUID(str(assistant_id)))
    if not isinstance(assistant, dict):
        raise TypeError("the run has no assistant message")
    calls = _calls(store, run_id)
    return score_observation(
        task,
        calls=calls,
        answer=str(assistant.get("text") or ""),
        status=str(run.get("status") or ""),
    )


def _install_dry_run(store: ChatService) -> None:
    completer = DryRunCompleter()

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        return await completer(messages, tools, tenant_id=tenant_id, model_alias=model_alias)

    def completion_call(
        tenant_id: uuid.UUID, alias: str = "reasoning"
    ) -> tuple[str, dict[str, str], float, bool]:
        del tenant_id, alias
        return "gym-dry-run", {}, 1.0, True

    def url_for(tenant_id: uuid.UUID, alias: str, headers: dict[str, str]) -> str:
        del tenant_id, alias, headers
        return "http://127.0.0.1:9/v1/chat/completions"

    store.complete_turn = complete  # type: ignore[method-assign]
    store._completion_call = completion_call  # type: ignore[method-assign]
    store._completion_url_for = url_for  # type: ignore[method-assign]


def _calls(store: ChatService, run_id: uuid.UUID) -> list[ObservedCall]:
    rows = [
        row
        for row in store.tool_calls.values()
        if row.get("run_id") == run_id and isinstance(row, dict)
    ]
    rows.sort(key=lambda row: str(row.get("created_at") or ""))
    found: list[ObservedCall] = []
    for row in rows:
        arguments = row.get("arguments_redacted")
        payload = arguments if isinstance(arguments, dict) else {}
        found.append(
            ObservedCall(
                name=str(row.get("qualified_name") or ""),
                arguments=payload,
                result_text=str(row.get("result_preview") or ""),
                status=str(row.get("status") or ""),
            )
        )
    return found


def _names(store: ChatService, file_ids: list[uuid.UUID]) -> list[str]:
    names: list[str] = []
    for file_id in file_ids:
        row = store.files.get(file_id)
        if isinstance(row, dict):
            names.append(str(row.get("name") or "upload"))
    return names
