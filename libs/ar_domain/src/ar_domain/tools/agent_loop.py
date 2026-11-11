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
from ar_domain.tools.gateway_client import execute_tool
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
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    user_text: str,
    *,
    one_step: bool = False,
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
    # Above the threshold, offer the core tools, the tools closest to what the person asked
    # and the search tool; the full catalogue stays in by_name so a searched tool resolves,
    # and its schema joins the next call.
    deferred = bool(catalog.get("tool_search_active"))
    offered: set[str] = {_spec_name(spec) for spec in openai_tools}
    if deferred:
        core = [row for row in tools if str(row.get("qualified_name")) in _CORE_WHEN_SEARCHING]
        core.extend(_closest(store, version_id, user_id, user_text, core))
        if not any(str(row.get("qualified_name")) == "session.search" for row in core):
            search_row = _search_tool_row(store)
            if search_row is not None:
                core.append(search_row)
                by_name[str(search_row["model_name"])] = search_row
                by_name[str(search_row["qualified_name"])] = search_row
        openai_tools = [_openai_tool(row) for row in core]
        openai_tools.extend(extra_tools)
        offered = {_spec_name(spec) for spec in openai_tools}
    from ar_common.logging import get_logger  # noqa: PLC0415

    # Tool names are not content. This is how a turn's choice of tool is explained later.
    get_logger(__name__).info("tools_offered", run_id=str(run.get("id")), names=sorted(offered))
    from ar_domain.tools.structured import schema_for  # noqa: PLC0415

    schema = schema_for(definition, run.get("response_format"))
    from ar_domain.tools.worker_loop import (  # noqa: PLC0415
        apply_worker_loop,
        consume_one_tool,
        read_worker_loop,
        snapshot,
        write_worker_loop,
    )

    saved_loop = read_worker_loop(run)
    resumed_loop = (
        apply_worker_loop(saved_loop)
        if isinstance(saved_loop, dict) and isinstance(saved_loop.get("messages"), list)
        else None
    )
    restored = None if resumed_loop is not None else restore_checkpoint(run)
    messages: list[dict[str, object]]
    previews: list[dict[str, object]]
    if resumed_loop is not None:
        messages = resumed_loop["messages"]
        steps = resumed_loop["steps"]
        used_calls = resumed_loop["used_calls"]
        tokens = resumed_loop["tokens"]
        tokens_in_total = resumed_loop["tokens_in_total"]
        tokens_out_total = resumed_loop["tokens_out_total"]
        prompt_seen = resumed_loop["prompt_seen"]
        cost = resumed_loop["cost"]
        previews = resumed_loop["previews"]
        user_text = str(resumed_loop["user_text"] or user_text)
        started = resumed_loop["started"]
        repairs = resumed_loop["repairs"]
        consecutive_errors = resumed_loop["consecutive_errors"]
        planned = resumed_loop["planned"]
        failed_open = resumed_loop["failed_open"]
    elif restored is None:
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
        repairs = 0
        consecutive_errors = 0
        planned = False
        failed_open = False
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
        consecutive_errors = 0
        planned = False
        failed_open = False
    provider_retries = 0
    from ar_domain.loop.planning import planning_enabled  # noqa: PLC0415
    from ar_domain.loop.repair import output_repair_limit, tool_failure_limit  # noqa: PLC0415

    repair_cap = output_repair_limit(definition)
    failure_cap = tool_failure_limit(definition)
    while True:
        if isinstance(saved_loop, dict) and saved_loop.get("phase") == "tools":
            kind = await consume_one_tool(
                store,
                run,
                assistant,
                saved_loop,
                by_name=by_name,
                limits=limits,
                alias=alias,
                deferred=deferred,
                openai_tools=openai_tools,
                offered=offered,
            )
            write_worker_loop(run, saved_loop)
            applied = apply_worker_loop(saved_loop)
            messages = applied["messages"]
            steps = applied["steps"]
            used_calls = applied["used_calls"]
            tokens = applied["tokens"]
            tokens_in_total = applied["tokens_in_total"]
            tokens_out_total = applied["tokens_out_total"]
            prompt_seen = applied["prompt_seen"]
            cost = applied["cost"]
            previews = applied["previews"]
            consecutive_errors = applied["consecutive_errors"]
            failed_open = applied["failed_open"]
            started = applied["started"]
            run["step_kind"] = kind
            saved_loop = read_worker_loop(run)
            if one_step or kind in {"paused", "final"}:
                return True
            if kind == "tools":
                continue
        steps += 1
        limit = _over(limits, steps, tokens, cost, started, used_calls)
        if limit is not None:
            # What was spent before the stop still counts.
            _remember_usage(run, tokens_in_total, tokens_out_total, cost, steps - 1)
            _stop_budget(store, run, assistant, limit)
            return True
        if planning_enabled(definition) and (not planned or run.get("needs_replan")):
            planned = await _take_plan(
                store, run, messages, alias, repairing=bool(run.get("needs_replan"))
            )
            run["needs_replan"] = False
        messages = _fit_context(store, run, messages, limits)
        turn = await store.complete_turn(
            messages,
            openai_tools,
            tenant_id=uuid.UUID(str(run["tenant_id"])),
            model_alias=alias,
        )
        if isinstance(turn, dict):
            _note_endpoint(store, run, turn, steps)
            _emit_reasoning(store, run, assistant, definition, turn)
        if isinstance(turn, dict) and turn.get("parse_error"):
            if repairs < repair_cap:
                repairs += 1
                messages.append(
                    {
                        "role": "user",
                        "content": _repair_text("parse", str(turn.get("parse_error"))),
                    }
                )
                _audit(
                    store,
                    run,
                    "run.retried",
                    str(run.get("id")),
                    {"reason": "parse"},
                    outcome="failure",
                )
                _emit_repair(store, run, "parse")
                continue
            _stop_error(store, run, assistant, _terminal_text(), code="repair_exhausted")
            return True
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
                _emit_repair(store, run, "provider")
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
                from ar_domain.tools.structured import accept_output  # noqa: PLC0415

                canonical, problem = accept_output(answer, schema)
                if canonical is not None:
                    answer = canonical
                if problem and repairs < repair_cap:
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
                    _emit_repair(store, run, "structured_output")
                    continue
            answer = _checked(store, run, answer, failed_open=failed_open, tool_calls=used_calls)
            _remember_usage(run, tokens_in_total, tokens_out_total, cost, steps)
            followups = await _followups(store, run, definition, user_text, answer)
            _finish(store, run, assistant, answer, previews, followups=followups)
            return True
        if not planned:
            _plan(store, run, calls)
            planned = True
        messages.append({"role": "assistant", "content": None, "tool_calls": _wire_calls(calls)})
        if one_step:
            write_worker_loop(
                run,
                snapshot(
                    messages=messages,
                    steps=steps,
                    used_calls=used_calls,
                    tokens=tokens,
                    tokens_in=tokens_in_total,
                    tokens_out=tokens_out_total,
                    prompt_seen=prompt_seen,
                    cost=cost,
                    previews=previews,
                    elapsed_s=time.monotonic() - started,
                    user_text=user_text,
                    repairs=repairs,
                    consecutive_errors=consecutive_errors,
                    planned=planned,
                    failed_open=failed_open,
                    phase="tools",
                    pending_calls=calls,
                ),
            )
            run["step_kind"] = "tools"
            return True
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
                invalid = _invalid_args(by_name.get(name), call)
                if invalid:
                    repairs += 1
                    outcome = _schema_outcome(call, name, invalid, used_calls)
                    _audit(
                        store,
                        run,
                        "run.retried",
                        str(call.get("id") or ""),
                        {"reason": "schema"},
                        outcome="failure",
                    )
                    if repairs > repair_cap:
                        _stop_error(
                            store, run, assistant, _terminal_text(), code="repair_exhausted"
                        )
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
            if failed and planning_enabled(definition):
                run["needs_replan"] = True
                planned = False
            if consecutive_errors >= failure_cap:
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


def _closest(
    store: Any,
    version_id: uuid.UUID,
    user_id: uuid.UUID,
    request: str,
    held: list[dict[str, object]],
) -> list[dict[str, object]]:
    """The agent's tools ranked closest to the request, up to its ``tool_search.top_k``.

    The same ranking ``session.search`` uses. A turn with no text adds nothing.
    """
    if not request.strip():
        return []
    ranked = (
        ToolPipeline(store)
        .resolve_catalog(agent_version_id=version_id, user_id=user_id, query=request)
        .get("tools")
    )
    have = {str(row.get("qualified_name")) for row in held}
    return [
        row
        for row in (ranked if isinstance(ranked, list) else [])
        if isinstance(row, dict) and str(row.get("qualified_name")) not in have
    ]


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


def _repair_text(kind: str, detail: str) -> str:
    from ar_domain.loop.repair import repair_prompt  # noqa: PLC0415

    return repair_prompt(kind, detail)


def _terminal_text() -> str:
    from ar_domain.loop.repair import TERMINAL  # noqa: PLC0415

    return TERMINAL


def _fit_context(
    store: Any, run: dict[str, object], messages: list[dict[str, object]], limits: dict[str, int]
) -> list[dict[str, object]]:
    from ar_domain.loop.context import context_book, fit_messages  # noqa: PLC0415

    fitted, note = fit_messages(
        messages, max_tokens=limits["max_tokens"], retained=context_book(run)
    )
    if note is not None:
        run["compaction"] = note
        store._emit(run, "context.compacted", note)
    return fitted


def _note_endpoint(store: Any, run: dict[str, object], turn: dict[str, object], step: int) -> None:
    endpoint = turn.get("endpoint_id")
    model = turn.get("answered_model")
    resolved = turn.get("resolved_model_id")
    if isinstance(resolved, str) and resolved:
        run["resolved_model_id"] = resolved
    if isinstance(model, str) and model:
        run["answered_model"] = model
        assistant = store.messages.get(run.get("assistant_message_id"))
        if isinstance(assistant, dict):
            assistant["answered_model"] = model
            assistant["model_alias"] = model_alias_for(store, run)
            registry = turn.get("model_id")
            if registry:
                assistant["model_id"] = registry
                run["model_id"] = registry
            if isinstance(resolved, str) and resolved:
                assistant["resolved_model_id"] = resolved
    if turn.get("fallback") is True:
        store._emit(
            run,
            "warning",
            {
                "code": "model_fallback_used",
                "message": "A fallback model answered this step.",
            },
        )
    if not isinstance(endpoint, str) or not endpoint:
        return
    trace = run.get("model_trace")
    rows = list(trace) if isinstance(trace, list) else []
    rows.append({"step": step, "endpoint_id": endpoint, "model": str(model or "")})
    run["model_trace"] = rows
    _audit(
        store,
        run,
        "run.model_answered",
        str(run.get("id")),
        {"step": step, "endpoint_id": endpoint, "model": str(model or "")},
    )


def _invalid_args(bound: dict[str, object] | None, call: dict[str, object]) -> str | None:
    if not isinstance(bound, dict):
        return None
    schema = bound.get("parameters")
    if not isinstance(schema, dict):
        schema = bound.get("input_schema")
    if not isinstance(schema, dict):
        return None
    arguments = call.get("arguments")
    payload = arguments if isinstance(arguments, dict) else {}
    from ar_domain.tools.logic import schema_errors  # noqa: PLC0415

    return schema_errors(schema, payload)


def _schema_outcome(
    call: dict[str, object], name: str, detail: str, attempt: int
) -> dict[str, object]:
    text = _repair_text("schema", detail)
    return {
        "failed": True,
        "preview": {
            "qualified_name": name,
            "status": "failed",
            "result_preview": text,
            "attempt": attempt,
            "error": {"code": "validation_failed", "message": detail},
        },
        "wrapped": wrap_tool_result(
            tool=name or "tool", call_id=str(call.get("id") or ""), content=text
        ),
        "images": [],
        "structured": {},
    }


async def _take_plan(
    store: Any,
    run: dict[str, object],
    messages: list[dict[str, object]],
    alias: str,
    *,
    repairing: bool,
) -> bool:
    from ar_domain.loop.planning import PLAN_INSTRUCTION, parse_plan, replan_instruction  # noqa: PLC0415

    prompt = PLAN_INSTRUCTION
    if repairing:
        prompt = replan_instruction("a tool call failed")
    turn = await store.complete_turn(
        [*messages, {"role": "user", "content": prompt}],
        [],
        tenant_id=uuid.UUID(str(run["tenant_id"])),
        model_alias=alias,
    )
    text = str(turn.get("text") or "") if isinstance(turn, dict) else ""
    items, error = parse_plan(text)
    if items is None:
        items = [{"id": "1", "title": "Answer the request", "status": "in_progress"}]
        error = error or "plan was not JSON"
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["plan"] = items
    store._emit(run, "plan.updated", {"items": items})
    _audit(
        store,
        run,
        "run.planned",
        str(run.get("id")),
        {"count": len(items), "replan": repairing, "parse_error": error},
    )
    return True


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
        conversation["plan"] = items
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
    result = execute_tool(
        store,
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
            "step": attempt,
            "call_index": attempt,
            "query_id": run.get("query_id"),
        },
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


def _checked(
    store: Any, run: dict[str, object], answer: str, *, failed_open: bool, tool_calls: int
) -> str:
    from ar_domain.loop.repair import acknowledges_failure, apply_tool_failure  # noqa: PLC0415

    hidden = failed_open and not acknowledges_failure(answer)
    if hidden:
        answer = f"{answer}\n\nA tool call failed and was not recovered."
    assistant = store.messages.get(run.get("assistant_message_id"))
    notice = None
    if isinstance(assistant, dict):
        notice = apply_tool_failure(assistant, failed_open=failed_open)
    if notice is not None:
        store._emit(run, "warning", {"code": notice["code"], "message": notice["message"]})
    _audit(
        store,
        run,
        "run.checked",
        str(run.get("id")),
        {"tool_calls": tool_calls, "recovered": not failed_open},
        outcome="failure" if failed_open else "success",
    )
    return answer


def _artifact_parts(store: Any, previews: list[dict[str, object]]) -> list[dict[str, object]]:
    """File and image parts a tool stored, once each, so :run can return the chart."""
    parts: list[dict[str, object]] = []
    seen: set[str] = set()
    files = getattr(store, "files", {})
    for preview in previews:
        presentation = preview.get("presentation") if isinstance(preview, dict) else None
        listed = presentation.get("files") if isinstance(presentation, dict) else None
        if not isinstance(listed, list):
            continue
        for item in listed:
            if not isinstance(item, dict):
                continue
            file_id = str(item.get("file_id") or item.get("fileId") or "")
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            meta = files.get(file_id) if isinstance(files, dict) else None
            if not isinstance(meta, dict):
                try:
                    meta = files.get(uuid.UUID(file_id)) if isinstance(files, dict) else None
                except ValueError:
                    meta = None
            name = str((meta or {}).get("name") or item.get("name") or "")
            mime = str((meta or {}).get("mime_type") or item.get("mime_type") or "")
            kind = "image" if mime.startswith("image/") or name.lower().endswith(".png") else "file"
            parts.append(
                {
                    "type": kind,
                    "file_id": file_id,
                    "name": name,
                    "mime_type": mime or "application/octet-stream",
                }
            )
    return parts


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


def _emit_repair(store: Any, run: dict[str, object], reason: str) -> None:
    store._emit(
        run,
        "warning",
        {"code": "repair", "message": f"The step was sent back for another try ({reason})."},
    )


def _show_reasoning(definition: dict[str, object] | None) -> bool:
    output = definition.get("output") if isinstance(definition, dict) else None
    if not isinstance(output, dict):
        return False
    return output.get("show_reasoning") is True or output.get("showReasoning") is True


def _emit_reasoning(
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    definition: dict[str, object] | None,
    turn: dict[str, object],
) -> None:
    if not _show_reasoning(definition):
        return
    text = turn.get("reasoning")
    if not isinstance(text, str) or not text.strip():
        return
    assistant["reasoning"] = text.strip()
    store._emit(
        run,
        "reasoning.delta",
        {"message_id": str(assistant.get("id") or ""), "text": text.strip()},
    )


async def _followups(
    store: Any,
    run: dict[str, object],
    definition: dict[str, object] | None,
    user_text: str,
    answer: str,
) -> list[str]:
    from ar_domain.loop.followups import suggest_followups  # noqa: PLC0415

    return await suggest_followups(store, run, definition, user_text, answer)


def _finish(
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    answer: str,
    previews: list[dict[str, object]],
    *,
    followups: list[str] | None = None,
) -> None:
    assistant["text"] = answer
    content = [*_with_trace(answer, run), *_artifact_parts(store, previews)]
    prompts = [item for item in (followups or []) if item.strip()]
    if prompts:
        content.append({"type": "followups", "prompts": prompts})
    assistant["content"] = content
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
    completed: dict[str, object] = {"message_id": str(assistant_id), "text": answer}
    answered = assistant.get("answered_model") or run.get("answered_model")
    if isinstance(answered, str) and answered:
        completed["answered_model"] = answered
    store._emit(run, "message.completed", completed)
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
