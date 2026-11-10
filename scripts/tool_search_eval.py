"""Check how well a tenant's embedding model ranks an agent's tools.

Tool search ranks tools by meaning, with the embedding model the tenant registered, and by
shared words (``ar_domain/tools/search.py``). This reads one agent's tools from the tenant's
database, ranks them for a set of requests, and prints where the tool a careful reader would
pick came out. Run it after changing tool descriptions or the ranking, and before pointing
the ``embed`` alias at another model.

    uv run python scripts/tool_search_eval.py --tenant acme --agent assistant
    uv run python scripts/tool_search_eval.py --tenant acme --all

``--all`` ranks every tool the tenant can search, which is what ``session.search`` does. A
request whose tool is not among those ranked is left out. Exit code 1 when a wanted tool is
ranked below ``--within`` (the number of tools an agent is offered by default).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from ar_domain.chat.service import ChatService
from ar_domain.db.engine import app_database_url
from ar_domain.durable.bind import TenantBinding, bind_store
from ar_domain.tools.handlers import searchable_tools
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.search import DEFAULT_TOP_K, prepare_tools, rank_tools

# A request, and the tools that would serve it.
CASES: list[tuple[str, set[str]]] = [
    ("What does the page at https://example.com say?", {"general.fetch"}),
    ("Turn this table into an Excel file with totals", {"documents.create"}),
    ("Read the text in this scanned invoice photo", {"documents.ocr", "image.ask"}),
    (
        "How many rows in the orders CSV have status shipped?",
        {"general.code", "documents.tables"},
    ),
    ("Look up the latest news about the Lyon transport strike", {"general.search"}),
    ("Run a Python script that sorts these numbers", {"general.code"}),
    ("Save these notes as a text file in my workspace", {"general.write_file"}),
    (
        "Which statements in this list have no supporting passage?",
        {"documents.missing"},
    ),
    ("What changed between the March and April versions of the contract?", {"documents.compare"}),
    ("Hide the names and phone numbers in this letter", {"documents.redact"}),
    ("Give me a short overview of the annual report", {"documents.summarise"}),
    ("What is in this chart screenshot?", {"image.ask"}),
    ("Post this JSON to our billing API", {"general.http"}),
    ("Which files did I upload to this chat?", {"general.list_files"}),
    ("Does our policy meet every statement in this rule set?", {"documents.judge"}),
    ("Pull the invoice number, date and total out of this PDF", {"documents.extract"}),
    ("Install nothing, just show me the disk usage with du", {"general.shell"}),
    ("Add the uploaded handbook to the library", {"documents.ingest"}),
    ("Show me the steps you intend to take", {"session.plan_update"}),
    ("Make the introduction of the proposal clearer", {"documents.rewrite"}),
    ("Quelle est la météo à Paris aujourd'hui ?", {"general.search", "general.fetch"}),
    ("Resume este documento en tres puntos", {"documents.summarise"}),
]


async def run(tenant_slug: str, agent_slug: str | None, within: int) -> int:
    """Rank the tools for every case; the number of cases that missed."""
    store = ChatService(fake_models_allowed=False)
    binding = await bind_store(store, app_database_url(), tenant_slug=tenant_slug)
    if binding is None:
        raise SystemExit("The database did not answer.")
    try:
        if agent_slug is None:
            tools = searchable_tools(store, str(binding.tenant_id))
        else:
            tools = _agent_tools(store, binding, agent_slug)
        return _report(store, binding.tenant_id, tools, within)
    finally:
        if store.durable_engine is not None:
            await store.durable_engine.dispose()


def _report(
    store: ChatService, tenant_id: object, tools: list[dict[str, object]], within: int
) -> int:
    names = {str(tool.get("qualified_name")) for tool in tools}
    # A search in the product never waits for the catalogue's vectors. This check does.
    prepared = prepare_tools(store, tenant_id, tools, wait=True)
    print(
        f"{len(tools)} tools, {'embedded' if prepared else 'no embedding model: ranked by words'}"
    )
    ranks: list[int] = []
    for request, wanted in CASES:
        if not wanted & names:
            print(f"   -  {request}  (none of {', '.join(sorted(wanted))} is among these tools)")
            continue
        ranked, how = rank_tools(store, tenant_id, request, tools)
        order = [str(tool.get("qualified_name")) for _score, tool in ranked]
        rank = min(order.index(name) for name in wanted & names) + 1
        ranks.append(rank)
        print(f"  {rank:2d}  {request}  [{how}; first: {order[0]}]")
    if not ranks:
        raise SystemExit("No case names one of these tools.")
    missed = sum(rank > within for rank in ranks)
    print(
        f"first {sum(rank == 1 for rank in ranks)}/{len(ranks)}, "
        f"in the first 5 {sum(rank <= 5 for rank in ranks)}/{len(ranks)}, "
        f"in the first {within} {len(ranks) - missed}/{len(ranks)}, lowest {max(ranks)}"
    )
    return missed


def _agent_tools(
    store: ChatService, binding: TenantBinding, agent_slug: str
) -> list[dict[str, object]]:
    """Every tool bound to the agent's published version, as a user of the tenant sees them."""
    if not binding.users:
        raise SystemExit("This tenant has no user to read the catalogue as.")
    reader = next(iter(binding.users.values()))
    published = next(
        (
            row.get("published_version_id")
            for row in store.agents.values()
            if row.get("slug") == agent_slug and row.get("tenant_id") == binding.tenant_id
        ),
        None,
    )
    if not isinstance(published, uuid.UUID) or published not in store.versions:
        raise SystemExit(f"No published agent '{agent_slug}' in this tenant.")
    catalog = ToolPipeline(store).resolve_catalog(agent_version_id=published, user_id=reader)
    found = catalog.get("tools")
    return [row for row in found if isinstance(row, dict)] if isinstance(found, list) else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank one agent's tools for a set of requests")
    parser.add_argument("--tenant", required=True, help="the tenant's slug")
    parser.add_argument("--agent", default="assistant", help="the agent's slug")
    parser.add_argument(
        "--all", action="store_true", help="rank every tool the tenant can search, not one agent's"
    )
    parser.add_argument("--within", type=int, default=DEFAULT_TOP_K)
    args = parser.parse_args()
    agent = None if args.all else args.agent
    raise SystemExit(1 if asyncio.run(run(args.tenant, agent, args.within)) else 0)


if __name__ == "__main__":
    main()
