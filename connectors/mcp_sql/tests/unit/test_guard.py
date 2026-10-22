"""The SQL guard rejects the malicious corpus and still allows a single select."""

from pathlib import Path

from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from ar_mcp_sql.guard import SqlRejected, check_sql
from ar_mcp_sql.main import create_application
from ar_mcp_sql.server import handle

_CORPUS = Path(__file__).parents[1] / "corpus" / "malicious.txt"


def test_corpus_has_at_least_two_hundred_rejects() -> None:
    samples = [line for line in _CORPUS.read_text().splitlines() if line.strip()]
    assert len(samples) >= 200
    for sample in samples:
        try:
            check_sql(
                sample, allow_tables={"public.orders"}, deny_columns={"public.orders.password"}
            )
        except SqlRejected:
            continue
        raise AssertionError(sample)


def test_count_query_is_rewritten_and_callable() -> None:
    sql = check_sql(
        "SELECT count(*) FROM public.orders", allow_tables={"public.orders"}, deny_columns=set()
    )
    assert "LIMIT" in sql.upper()
    body = handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "run_query",
                "arguments": {"sql": "SELECT count(*) FROM public.orders"},
            },
        }
    )
    text = body["result"]["content"][0]["text"]
    assert text == "3"


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=24))
def test_unknown_words_do_not_become_a_select(word: str) -> None:
    statement = f"{word} public.orders"
    if statement.lower().startswith("select "):
        return
    try:
        check_sql(statement, allow_tables={"public.orders"}, deny_columns=set())
    except SqlRejected:
        return
    raise AssertionError(statement)


def test_http_entrypoint_lists_and_rejects_writes() -> None:
    client = TestClient(create_application())
    listed = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert listed.status_code == 200
    assert listed.json()["result"]["tools"]
    probe = client.post(
        "/internal/v1/connections:test",
        json={"sql": "DROP TABLE public.orders", "allowTables": ["public.orders"]},
    )
    assert probe.status_code == 200
    assert probe.json()["ok"] is False
