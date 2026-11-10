"""Plan, act, check and retry. Spec: docs/03-specs/07-agent-runtime.md.

A fake provider leaves the turn on the existing path. A real provider, or a
test that marks the call real, owns the turn: the model sees tool results,
a failed call is sent back for another attempt, and every step is traced.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import TYPE_CHECKING

from ar_common.offload import run_sync
from ar_common.time import utcnow
from ar_common.wrapping import wrap_tool_result
from ar_domain.runs.failure import fail_run
from ar_domain.runs.logic import budget_exceeded
from ar_domain.tools.images import build_image_message, collect_images
from ar_domain.tools.logic import call_args_hash
from ar_domain.tools.pipeline import ToolPipeline

if TYPE_CHECKING:
    from typing import Any


def model_alias_for(store: Any, run: dict[str, object]) -> str:
    """Conversation choice, then the agent alias, then reasoning."""
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        chosen = conversation.get("model_alias")
        if isinstance(chosen, str) and chosen.strip():
            return chosen.strip()
    version = store.versions.get(run.get("agent_version_id"))
    definition = version.get("definition") if isinstance(version, dict) else None
    model = definition.get("model") if isinstance(definition, dict) else None
    if isinstance(model, dict):
        alias = model.get("alias")
        if isinstance(alias, str) and alias.strip():
            return alias.strip()
    return "reasoning"


def read_budget(
    definition: dict[str, object], run: dict[str, object] | None = None
) -> dict[str, int]:
    """Customer limits, with the platform defaults for anything omitted."""
    raw = definition.get("budget")
    source = raw if isinstance(raw, dict) else {}
    defaults = {
        "max_steps": 8,
        "max_tokens": 16000,
        "max_cost_micros": 1_000_000,
        "max_wall_clock_s": 120,
        "max_tool_calls": 8,
    }
    limits: dict[str, int] = {}
    for key, default in defaults.items():
        value = source.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            limits[key] = default
        else:
            limits[key] = value
    override = run.get("budget_override") if isinstance(run, dict) else None
    if isinstance(override, dict):
        for key, value in override.items():
            if key in limits and isinstance(value, int) and not isinstance(value, bool):
                limits[key] = min(limits[key], value)
    return limits


async def run_agent_loop(  # noqa: PLR0911, PLR0912, PLR0915
    store: Any, run: dict[str, object], assistant: dict[str, object], user_text: str
) -> bool:
    """Run the model loop. Return false when a fake provider should answer alone."""
    definition = _definition(store, run)
    if definition is None:
        return False
    limits = read_budget(definition, run)
    if limits["max_tool_calls"] <= 0 and not run.get("orchestration_child"):
        return False
    alias = model_alias_for(store, run)
    _model, _headers, _timeout, real = store._completion_call(
        uuid.UUID(str(run["tenant_id"])), alias
    )
    if not real:
        if getattr(store, "fake_models_allowed", True):
            return False
        # Outside dev and CI an alias that resolves to the local fake must not echo
        # the prompt back as an answer (fresh-pass defect 5).
        _stop_error(
            store,
            run,
            assistant,
            f"The model alias '{alias}' is not connected to a registered model. "
            "Open Models and point the alias at a provider.",
            code="model_unavailable",
        )
        return True
    version_id = run.get("agent_version_id")
    user_id = run.get("user_id")
    if not isinstance(version_id, uuid.UUID) or not isinstance(user_id, uuid.UUID):
        return False
    catalog = ToolPipeline(store).resolve_catalog(agent_version_id=version_id, user_id=user_id)
    raw_tools = catalog.get("tools")
    tools = (
        [row for row in raw_tools if isinstance(row, dict)] if isinstance(raw_tools, list) else []
    )
    from ar_domain.orchestration.engine import (  # noqa: PLC0415
        ORCHESTRATION_NAMES,
        orchestration_tools,
        restore_checkpoint,
        save_checkpoint,
    )
    from ar_domain.workspace.turn import has_grounding, opening_messages  # noqa: PLC0415

    extra_tools, extra_index = orchestration_tools(store, run, definition)
    if (
        not tools
        and not extra_tools
        and not has_grounding(definition)
        and not run.get("orchestration_child")
    ):
        return False
    by_name = _index(tools)
    by_name.update(extra_index)
    # The model chooses a skill: when the agent has skills, offer skills.load so it can
    # load the one the prompt lists, whether or not the agent binds the skills server.
    if definition.get("skills") and "skills.load" not in by_name:
        load_row = _catalogue_row(store, "skills.load", "skills__load")
        if load_row is not None:
            tools = [*tools, load_row]
            by_name["skills__load"] = load_row
            by_name["skills.load"] = load_row
    openai_tools = [_openai_tool(row) for row in tools]
    openai_tools.extend(extra_tools)
    # Above the threshold, offer the core tools and the search tool; the full catalogue
    # stays in by_name so a searched tool resolves, and its schema joins the next call.
    deferred = bool(catalog.get("tool_search_active"))
    offered: set[str] = {_spec_name(spec) for spec in openai_tools}
    if deferred:
        core = [row for row in tools if str(row.get("qualified_name")) in _CORE_WHEN_SEARCHING]
        if not any(str(row.get("qualified_name")) == "session.search" for row in core):
            search_row = _search_tool_row(store)
            if search_row is not None:
                core.append(search_row)
                by_name[str(search_row["model_name"])] = search_row
                by_name[str(search_row["qualified_name"])] = search_row
        openai_tools = [_openai_tool(row) for row in core]
        openai_tools.extend(extra_tools)
        offered = {_spec_name(spec) for spec in openai_tools}
    from ar_domain.tools.structured import output_schema, validate_output  # noqa: PLC0415

    schema = output_schema(definition)
    restored = restore_checkpoint(run)
    messages: list[dict[str, object]]
    previews: list[dict[str, object]]
    if restored is None:
        messages = opening_messages(run, definition, user_text)
        steps = 0
        used_calls = 0
        tokens = 0
        tokens_in_total = 0
        tokens_out_total = 0
        prompt_seen = 0
        cost = 0
        previews = []
        started = time.monotonic()
    else:
        messages = restored["messages"]
        steps = restored["steps"]
        used_calls = restored["used_calls"]
        tokens = restored["tokens"]
        tokens_in_total = restored["tokens_in"]
        tokens_out_total = restored["tokens_out"]
        prompt_seen = 0
        cost = restored["cost"]
        previews = restored["previews"]
        user_text = str(restored["user_text"] or user_text)
        started = time.monotonic() - restored["elapsed_s"]
    repairs = 0
    provider_retries = 0
    consecutive_errors = 0
    planned = False
    failed_open = False
    while True:
        steps += 1
        limit = _over(limits, steps, tokens, cost, started, used_calls)
        if limit is not None:
            # What was spent before the stop still counts.
            _remember_usage(run, tokens_in_total, tokens_out_total, cost, steps - 1)
            _stop_budget(store, run, assistant, limit)
            return True
        turn = await store.complete_turn(
            messages,
            openai_tools,
            tenant_id=uuid.UUID(str(run["tenant_id"])),
            model_alias=alias,
        )
        if not isinstance(turn, dict) or _provider_error(turn):
            if provider_retries < 2:
                provider_retries += 1
                await asyncio.sleep(0.2 * provider_retries)
                _audit(
                    store,
                    run,
                    "run.retried",
                    str(run.get("id")),
                    {"reason": "provider"},
                    outcome="failure",
                )
                continue
            _remember_usage(run, tokens_in_total, tokens_out_total, cost, steps)
            _stop_error(store, run, assistant, "The model provider did not answer.")
            return True
        provider_retries = 0
        raw_usage = turn.get("usage")
        usage = raw_usage if isinstance(raw_usage, dict) else {}
        step_in = _whole(usage.get("tokens_in"))
        step_out = _whole(usage.get("tokens_out"))
        # The provider reports the whole prompt every call. Usage and cost keep
        # that full count. The budget adds only the growth since the previous
        # prompt, plus this step's output, so a six-step tool turn fits in 16k.
        tokens, prompt_seen = _charge_budget(tokens, prompt_seen, step_in, step_out)
        tokens_in_total += step_in
        tokens_out_total += step_out
        step_cost, model_id = price_step(store, run, alias, step_in, step_out)
        cost += step_cost
        note_model_usage(
            store, run, alias, model_id, step=steps, tokens_in=step_in, tokens_out=step_out
        )
        calls = turn.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            answer = str(turn.get("text") or "").strip() or "The model returned an empty answer."
            if schema:
                problem = validate_output(answer, schema)
                if problem and repairs < 1:
                    repairs += 1
                    messages.append({"role": "assistant", "content": answer})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "That was not valid JSON for the required schema: "
                                f"{problem}. Reply with only the JSON object."
                            ),
                        }
                    )
                    _audit(
                        store,
                        run,
                        "run.retried",
                        str(run.get("id")),
                        {"reason": "structured_output"},
                        outcome="failure",
                    )
                    continue
            answer = _checked(store, run, answer, failed_open=failed_open, tool_calls=used_calls)
            _remember_usage(run, tokens_in_total, tokens_out_total, cost, steps)
            _finish(store, run, assistant, answer, previews)
            return True
        if not planned:
            _plan(store, run, calls)
            planned = True
        messages.append({"role": "assistant", "content": None, "tool_calls": _wire_calls(calls)})
        batch_images: list[dict[str, object]] = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            if used_calls >= limits["max_tool_calls"]:
                _stop_budget(store, run, assistant, "max_tool_calls")
                return True
            used_calls += 1
            name = str(call.get("name") or "")
            if name in ORCHESTRATION_NAMES:
                from ar_domain.orchestration.engine import handle_orchestration  # noqa: PLC0415

                state = {
                    "messages": messages,
                    "steps": steps,
                    "tokens": tokens,
                    "tokens_in": tokens_in_total,
                    "tokens_out": tokens_out_total,
                    "cost": cost,
                    "used_calls": used_calls,
                    "previews": previews,
                    "started": started,
                    "user_text": user_text,
                    "limits": limits,
                }
                outcome = await handle_orchestration(store, run, assistant, call, state)
                if outcome is None:
                    save_checkpoint(run, state, str(call.get("id") or "ask"))
                    await _flush_run(store)
                    return True
                added_tokens = outcome.get("tokens")
                added_cost = outcome.get("cost")
                if isinstance(added_tokens, int) and not isinstance(added_tokens, bool):
                    tokens += added_tokens
                if isinstance(added_cost, int) and not isinstance(added_cost, bool):
                    cost += added_cost
                if outcome.get("stop"):
                    _remember_usage(run, tokens_in_total, tokens_out_total, cost, steps)
                    _finish(store, run, assistant, str(outcome.get("answer") or ""), previews)
                    return True
            else:
                # The handler runs here, on the loop thread, and the loop goes on while
                # it waits for a network call or a command (ar_common.offload).
                outcome = await run_sync(
                    _act,
                    store,
                    run,
                    assistant,
                    call,
                    by_name,
                    used_calls,
                    retry=consecutive_errors > 0,
                    limit_s=_time_left(limits, started),
                )
            if outcome is None:
                return True
            failed = bool(outcome["failed"])
            failed_open = failed
            consecutive_errors = consecutive_errors + 1 if failed else 0
            preview = outcome["preview"]
            if isinstance(preview, dict):
                previews.append(preview)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(call.get("id") or ""),
                    "content": str(outcome["wrapped"]),
                }
            )
            produced = outcome.get("images")
            if isinstance(produced, list):
                batch_images.extend(produced)
            if deferred and str(call.get("name")) in _SEARCH_TOOL_NAMES:
                _add_found_tools(outcome.get("structured"), by_name, openai_tools, offered)
            if consecutive_errors >= 8:
                _stop_error(
                    store,
                    run,
                    assistant,
                    "The tool kept failing, so this run stopped.",
                )
                return True
        if batch_images:
            # Every tool call in the batch is answered above; only now may a user
            # message carry the pictures the batch produced to a model that can see
            # them (M40-T06). The vision-alias description path does a model call, so
            # it runs off the loop thread under the remaining time budget.
            shown = await run_sync(
                build_image_message,
                store,
                run,
                batch_images,
                alias=alias,
                limit_s=_time_left(limits, started),
            )
            if isinstance(shown, dict):
                messages.append(shown)


def _provider_error(turn: dict[str, object]) -> bool:
    calls = turn.get("tool_calls")
    if isinstance(calls, list) and calls:
        return False
    text = str(turn.get("text") or "")
    return text.startswith("The model provider")


async def _flush_run(store: Any) -> None:
    if getattr(store, "durable_engine", None) is None:
        return
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415

    await flush_store(store)


def _remember_usage(
    run: dict[str, object], tokens_in: int, tokens_out: int, cost: int, steps: int
) -> None:
    run["usage"] = {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_micros": cost,
        "steps": steps,
    }


def _whole(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def _charge_budget(tokens: int, prompt_seen: int, step_in: int, step_out: int) -> tuple[int, int]:
    """Return the new budget total and the prompt size just reported.

    ``step_in`` is the whole prompt. Only the tokens that were not in the
    previous prompt count, together with this step's output.
    """
    growth = step_in if prompt_seen <= 0 else max(0, step_in - prompt_seen)
    return tokens + growth + step_out, step_in


def price_step(
    store: Any, run: dict[str, object], alias: str, tokens_in: int, tokens_out: int
) -> tuple[int, str | None]:
    """Cost of one model call from the resolved model's prices (spec 17 §2)."""
    pricing = getattr(store, "model_cost", None)
    if pricing is None:
        return 0, None
    try:
        tenant_id = uuid.UUID(str(run.get("tenant_id")))
    except ValueError:
        return 0, None
    cost, model_id = pricing(tenant_id, alias, tokens_in, tokens_out)
    return int(cost), model_id


def note_model_usage(
    store: Any,
    run: dict[str, object],
    alias: str,
    model_id: str | None,
    *,
    step: int | str,
    tokens_in: int,
    tokens_out: int,
) -> None:
    """One input and one output usage event per model call, priced separately.

    ``step`` is the loop step, or a name for a call outside the loop (``memory``).
    """
    from ar_domain.usage.logic import UsageRecord  # noqa: PLC0415
    from ar_domain.usage.service import note  # noqa: PLC0415

    tenant = str(run.get("tenant_id") or "")
    if not tenant or not hasattr(store, "usage"):
        return
    run_id = str(run.get("id"))
    now = utcnow()
    user = str(run["user_id"]) if run.get("user_id") else None
    agent = str(run["agent_id"]) if run.get("agent_id") else None
    in_cost, _ = price_step(store, run, alias, tokens_in, 0)
    out_cost, _ = price_step(store, run, alias, 0, tokens_out)
    for metric, quantity, cost, suffix in (
        ("model_input_tokens", tokens_in, in_cost, "in"),
        ("model_output_tokens", tokens_out, out_cost, "out"),
    ):
        note(
            store,
            UsageRecord(
                tenant,
                now,
                metric,
                quantity,
                cost,
                f"mg:{run_id}:{step}:{suffix}",
                user_id=user,
                agent_id=agent,
                model_alias=alias,
                source="model-gateway",
                run_id=run_id,
                model_id=model_id,
            ),
        )


def _definition(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    version = store.versions.get(run.get("agent_version_id"))
    definition = version.get("definition") if isinstance(version, dict) else None
    if not isinstance(definition, dict):
        return None
    return definition


def _index(tools: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    found: dict[str, dict[str, object]] = {}
    for row in tools:
        model_name = str(row.get("model_name") or "")
        qualified = str(row.get("qualified_name") or "")
        if model_name:
            found[model_name] = row
        if qualified:
            found[qualified] = row
    return found


def _openai_tool(row: dict[str, object]) -> dict[str, object]:
    parameters = row.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": str(row.get("model_name") or row.get("qualified_name") or "tool"),
            "description": str(row.get("description") or ""),
            "parameters": parameters,
        },
    }


# Above the tool-count threshold the model is sent these always-available tools and the
# search tool; it finds the rest with a search, and a found tool's schema is added to the
# next call (M39-T04).
_CORE_WHEN_SEARCHING = frozenset(
    {"files.read", "files.list", "session.plan_update", "session.search", "skills.load"}
)
_SEARCH_TOOL_NAMES = frozenset({"session__search", "tools__search"})


def _spec_name(spec: dict[str, object]) -> str:
    """The model-facing name of an OpenAI tool spec."""
    function = spec.get("function")
    return str(function.get("name")) if isinstance(function, dict) else ""


def _catalogue_row(store: Any, qualified: str, model_name: str) -> dict[str, object] | None:
    """A catalogue row for an always-available tool, so it can be offered unbound."""
    for row in getattr(store, "tool_versions", {}).values():
        if isinstance(row, dict) and row.get("qualified_name") == qualified:
            return {
                "model_name": model_name,
                "qualified_name": qualified,
                "description": row.get("description"),
                "parameters": row.get("input_schema"),
                "risk_class": row.get("risk_class"),
                "tool_version_id": str(row.get("id")),
            }
    return None


def _search_tool_row(store: Any) -> dict[str, object] | None:
    """The catalogue row for ``session.search``, so the search tool can always be offered."""
    return _catalogue_row(store, "session.search", "session__search")


def _add_found_tools(
    structured: object,
    by_name: dict[str, dict[str, object]],
    openai_tools: list[dict[str, object]],
    offered: set[str],
) -> int:
    """Add a search result's tool schemas to the model's next call."""
    if not isinstance(structured, dict):
        return 0
    found = structured.get("tools")
    if not isinstance(found, list):
        return 0
    added = 0
    for item in found:
        qualified = str(item.get("qualified_name")) if isinstance(item, dict) else ""
        row = by_name.get(qualified)
        if not isinstance(row, dict):
            continue
        spec = _openai_tool(row)
        name = _spec_name(spec)
        if name in offered:
            continue
        openai_tools.append(spec)
        offered.add(name)
        added += 1
    return added


def _wire_calls(calls: list[object]) -> list[dict[str, object]]:
    import orjson  # noqa: PLC0415

    wired: list[dict[str, object]] = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            continue
        arguments = call.get("arguments")
        payload = arguments if isinstance(arguments, dict) else {}
        wired.append(
            {
                "id": str(call.get("id") or f"call_{index}"),
                "type": "function",
                "function": {
                    "name": str(call.get("name") or ""),
                    "arguments": orjson.dumps(payload).decode(),
                },
            }
        )
    return wired


def _time_left(limits: dict[str, int], started: float) -> float:
    """Seconds of the run's wall clock a tool call may still use, and never under one."""
    return max(1.0, limits["max_wall_clock_s"] - (time.monotonic() - started))


def _over(  # noqa: PLR0917
    limits: dict[str, int], steps: int, tokens: int, cost: int, started: float, tool_calls: int
) -> str | None:
    return budget_exceeded(
        steps=steps,
        tokens=max(tokens, 1),
        cost_micros=cost,
        elapsed_s=int(time.monotonic() - started),
        tool_calls=tool_calls,
        budget=limits,
    )


def _plan(store: Any, run: dict[str, object], calls: list[object]) -> None:
    items = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            continue
        name = str(call.get("name") or "tool").replace("__", ".")
        items.append({"id": str(index + 1), "title": name, "status": "in_progress"})
    if not items:
        return
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["plan"] = [str(item["title"]) for item in items]
    store._emit(run, "plan.updated", {"items": items})
    _audit(store, run, "run.planned", str(run.get("id")), {"count": len(items)})


def _act(  # noqa: PLR0917
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    call: dict[str, object],
    by_name: dict[str, dict[str, object]],
    attempt: int,
    *,
    retry: bool,
) -> dict[str, object] | None:
    name = str(call.get("name") or "")
    bound = by_name.get(name)
    arguments = call.get("arguments")
    payload = arguments if isinstance(arguments, dict) else {}
    model_call_id = str(call.get("id") or f"call_{attempt}")
    if bound is None:
        missing = {
            "qualified_name": name,
            "status": "failed",
            "result_preview": "That tool is not available to this agent.",
            "attempt": attempt,
        }
        store._emit(
            run,
            "tool_call.failed",
            {
                "tool_call_id": model_call_id,
                "qualified_name": name,
                "status": "failed",
                "attempt": attempt,
                "error": {"code": "not_found", "message": missing["result_preview"]},
            },
        )
        _audit(
            store,
            run,
            "tool.called",
            model_call_id,
            {"status": "failed", "attempt": attempt},
            outcome="failure",
        )
        return {
            "failed": True,
            "preview": missing,
            "wrapped": wrap_tool_result(
                tool=name or "tool",
                call_id=model_call_id,
                content="That tool is not available to this agent.",
            ),
        }
    qualified = str(bound.get("qualified_name") or name)
    version_id = uuid.UUID(str(bound["tool_version_id"]))
    digest = call_args_hash(str(version_id), payload)
    store._emit(
        run,
        "tool_call.started",
        {
            "tool_call_id": model_call_id,
            "model_call_id": model_call_id,
            "qualified_name": qualified,
            "title": qualified,
            "risk_class": bound.get("risk_class"),
            "attempt": attempt,
        },
    )
    result = ToolPipeline(store).execute(
        {
            "tenant_id": run.get("tenant_id"),
            "user_id": run.get("user_id"),
            "run_id": run.get("id"),
            "agent_id": run.get("agent_id"),
            "agent_version_id": run.get("agent_version_id"),
            "tool_version_id": version_id,
            "arguments": payload,
            "args_hash": digest,
            "model_call_id": model_call_id,
        }
    )
    if result.get("status") == "awaiting_approval":
        from ar_domain.tools.chat_loop import _pause  # noqa: PLC0415

        _pause(
            store,
            run,
            assistant,
            {
                "tool_version_id": version_id,
                "qualified_name": qualified,
                "risk_class": bound.get("risk_class"),
                "arguments": payload,
            },
            result,
            payload,
        )
        return None
    failed = result.get("status") != "succeeded"
    event = "tool_call.failed" if failed else "tool_call.completed"
    error_body = result.get("error")
    _audit(
        store,
        run,
        "tool.called",
        str(result.get("tool_call_id") or model_call_id),
        {"status": result.get("status"), "attempt": attempt, "args_hash": digest},
        outcome="failure" if failed else "success",
    )
    if retry:
        _audit(
            store,
            run,
            "run.retried",
            str(result.get("tool_call_id") or model_call_id),
            {"attempt": attempt},
            outcome="failure" if failed else "success",
        )
    text = str(result.get("result_preview") or "")
    if failed and isinstance(error_body, dict):
        text = str(error_body.get("message") or text)
    preview: dict[str, object] = {
        "qualified_name": qualified,
        "status": result.get("status"),
        "result_preview": result.get("result_preview"),
        "attempt": attempt,
        "error": error_body,
    }
    structured = result.get("structured")
    if isinstance(structured, dict) and isinstance(structured.get("presentation"), dict):
        preview["presentation"] = structured["presentation"]
    store._emit(
        run,
        event,
        {
            "tool_call_id": result.get("tool_call_id") or model_call_id,
            "qualified_name": qualified,
            "status": result.get("status"),
            "result_preview": result.get("result_preview"),
            "presentation": preview.get("presentation"),
            "error": error_body,
            "attempt": attempt,
            "latency_ms": result.get("latency_ms"),
        },
    )
    return {
        "failed": failed,
        "preview": preview,
        "wrapped": wrap_tool_result(tool=qualified, call_id=model_call_id, content=text or "empty"),
        "images": collect_images(store, structured, run.get("tenant_id")),
        "structured": structured,
    }


# Words that show the answer already tells the person a tool did not do its job, so the
# notice is not added on top. A refusal is phrased many ways ("blocked", "not permitted"),
# so the list is broad; a structured marker the UI renders is the longer-term approach
# (OQ-113).
_ACKNOWLEDGES_FAILURE = (
    "fail",
    "error",
    "could not",
    "couldn't",
    "cannot",
    "can't",
    "unable",
    "was not able",
    "wasn't able",
    "not able",
    "retry",
    "try again",
    "blocked",
    "refused",
    "denied",
    "rejected",
    "prevented",
    "not permitted",
    "not allowed",
    "no access",
    "unavailable",
    "not available",
    "did not work",
    "didn't work",
    "no result",
    "nothing was returned",
)


def _checked(
    store: Any, run: dict[str, object], answer: str, *, failed_open: bool, tool_calls: int
) -> str:
    hidden = failed_open and not any(word in answer.lower() for word in _ACKNOWLEDGES_FAILURE)
    if hidden:
        answer = f"{answer}\n\nA tool call failed and was not recovered."
    _audit(
        store,
        run,
        "run.checked",
        str(run.get("id")),
        {"tool_calls": tool_calls, "recovered": not failed_open},
        outcome="failure" if hidden else "success",
    )
    return answer


def _with_trace(answer: str, run: dict[str, object]) -> list[dict[str, object]]:
    from ar_domain.workspace.turn import citation_parts  # noqa: PLC0415

    return [{"type": "text", "text": answer}, *citation_parts(run.get("retrieval"))]


def _emit_trace(store: Any, run: dict[str, object], assistant_id: object) -> None:
    retrieval = run.get("retrieval")
    if isinstance(retrieval, dict):
        store._emit(
            run,
            "knowledge.retrieved",
            {
                "message_id": str(assistant_id),
                "used_chars": retrieval.get("used_chars"),
                "hits": len(retrieval.get("hits") or []),
            },
        )
    loaded = run.get("loaded_skill")
    if isinstance(loaded, dict):
        store._emit(
            run,
            "skill.loaded",
            {
                "message_id": str(assistant_id),
                "slug": loaded.get("slug"),
                "reason": loaded.get("reason"),
            },
        )


def _finish(
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    answer: str,
    previews: list[dict[str, object]],
) -> None:
    assistant["text"] = answer
    assistant["content"] = _with_trace(answer, run)
    assistant["retrieval"] = run.get("retrieval")
    assistant["loaded_skill"] = run.get("loaded_skill")
    assistant["tool_calls"] = previews
    assistant["status"] = "completed"
    run["status"] = "completed"
    run["ended_at"] = utcnow()
    run["result_summary"] = answer[:8000]
    usage = run.get("usage")
    if not isinstance(usage, dict) or "cost_micros" not in usage:
        usage = {
            "tokens_in": 1,
            "tokens_out": max(1, len(answer.split())),
            "cost_micros": 0,
            "steps": 1,
        }
        run["usage"] = usage
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["active_run_id"] = None
    assistant_id = assistant.get("id")
    _emit_trace(store, run, assistant_id)
    stored = run.get("usage")
    emitted = stored if isinstance(stored, dict) else {"tokens_in": 1, "tokens_out": 1}
    store._emit(run, "message.completed", {"message_id": str(assistant_id), "text": answer})
    store._emit(run, "run.completed", {"final_message_id": str(assistant_id), "usage": emitted})
    callback = run.get("callback_url")
    callbacks = getattr(store, "callbacks", None)
    if isinstance(callback, str) and callback and isinstance(callbacks, list):
        callbacks.append(
            {"url": callback, "run_id": str(run.get("id")), "status": "completed", "text": answer}
        )


def _stop_budget(
    store: Any, run: dict[str, object], assistant: dict[str, object], limit: str
) -> None:
    text = f"Stopped because the {limit.replace('_', ' ')} limit was reached."
    assistant["text"] = text
    assistant["content"] = [{"type": "text", "text": text}]
    assistant["status"] = "completed"
    run["status"] = "budget_exceeded"
    run["ended_at"] = utcnow()
    run["result_summary"] = text
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["active_run_id"] = None
    store._emit(run, "run.budget_exceeded", {"limit": limit})
    _audit(
        store, run, "run.budget_exceeded", str(run.get("id")), {"limit": limit}, outcome="failure"
    )


def _stop_error(
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    text: str,
    *,
    code: str = "model_error",
) -> None:
    fail_run(store, run, code=code, message=text, assistant=assistant)


_UNEXPECTED = "Something went wrong while working on this. The run was stopped."


def fail_unexpected(store: Any, run_id: object, exc: BaseException) -> bool:
    """End a run that an unexpected error left working. Return whether it was ended.

    The log carries the error type and where it was raised, never the message:
    an exception text can hold prompt or tool content.
    """
    from ar_common.logging import get_logger  # noqa: PLC0415
    from ar_domain.conversations.logic import run_is_working  # noqa: PLC0415
    from ar_domain.tools.logic import raised_at  # noqa: PLC0415

    get_logger(__name__).error(
        "run_failed_unexpectedly",
        run_id=str(run_id),
        error_type=type(exc).__name__,
        where=raised_at(exc),
    )
    run = store.runs.get(run_id)
    if not isinstance(run, dict) or not run_is_working(str(run.get("status"))):
        return False
    assistant = store.messages.get(run.get("assistant_message_id"))
    if not isinstance(assistant, dict):
        return False
    _stop_error(store, run, assistant, _UNEXPECTED, code="internal_error")
    return True


def _audit(
    store: Any,
    run: dict[str, object],
    action: str,
    target_id: str,
    detail: dict[str, object],
    *,
    outcome: str = "success",
) -> None:
    store.audit_log.append(
        {
            "tenant_id": str(run.get("tenant_id")),
            "actor_id": str(run.get("user_id")),
            "action": action,
            "target_type": "run",
            "target_id": target_id,
            "detail": detail,
            "outcome": outcome,
            "at": utcnow().isoformat(),
        }
    )
