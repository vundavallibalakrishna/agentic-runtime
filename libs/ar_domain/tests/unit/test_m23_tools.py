"""M23 database, spreadsheet, chart and structured-output tools."""

import asyncio
import uuid

import pytest

from ar_domain.demo_ids import demo_id
from ar_domain.tools.data_connections import DataConnections
from ar_domain.tools.database import (
    _find,
    _refuse_unsafe,
    _split_table,
    apply_read_only,
    clean_dsn,
    connection_dsn,
    dispatch_data,
)
from ar_domain.tools.general import dispatch_general
from ar_domain.tools.sql_guard import SqlRejected, check_sql
from ar_domain.tools.structured import output_schema, validate_output
from ar_testing.demo import demo_store


def test_sql_guard_rejects_writes_and_side_effects() -> None:
    denied = [
        "DROP TABLE stores",
        "DELETE FROM public.orders",
        "SELECT 1; DROP TABLE stores",
        "SELECT pg_sleep(10)",
        "SELECT lo_import('/tmp/x')",
        "COPY public.orders TO STDOUT",
        "WITH changed AS (INSERT INTO public.orders VALUES (1) RETURNING id) SELECT * FROM changed",
        "SELECT nextval('orders_id_seq')",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM secret.payroll",
    ]
    for sql in denied:
        with pytest.raises(SqlRejected):
            check_sql(sql, allow_tables={"public.orders"}, deny_columns=set(), allow_any=False)
    checked = check_sql(
        "SELECT id FROM public.orders",
        allow_tables={"public.orders"},
        deny_columns=set(),
        row_limit=2,
    )
    assert "LIMIT" in checked.upper()
    with pytest.raises(SqlRejected):
        _split_table("public.stores;drop")


def test_read_only_session_and_dsn_hygiene(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    apply_read_only(seen.append, 30000, mysql=False)
    assert "SET default_transaction_read_only = on" in seen
    assert "SET TRANSACTION READ ONLY" in seen
    mysql: list[str] = []
    apply_read_only(mysql.append, 1000, mysql=True)
    assert any("READ ONLY" in item for item in mysql)
    cleaned = clean_dsn(
        "postgresql://user:secret@db:5432/app?options=-cdefault_transaction_read_only%3Doff&sslmode=require"
    )
    assert "options" not in cleaned
    assert "sslmode=require" in cleaned
    monkeypatch.setenv("AR_DATABASE_URL", "postgresql://ar:pw@127.0.0.1:55440/agentic_runtime")
    with pytest.raises(SqlRejected, match="platform"):
        _refuse_unsafe("postgres://reader:pw@localhost:55440/agentic_runtime", {})
    _refuse_unsafe(
        "postgres://reader:pw@localhost:55440/agentic_runtime",
        {"allow_platform": True},
    )
    monkeypatch.setattr(
        "ar_domain.tools.database.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(0, 0, 0, "", ("169.254.169.254", 0))],
    )
    with pytest.raises(SqlRejected, match="link-local"):
        _refuse_unsafe("postgresql://reader:pw@metadata.example:5432/analysis", {})


def test_connection_secrets_stay_sealed_and_real_names_win() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    from ar_domain.agents.access import Actor

    actor = Actor(tenant, user, frozenset({"tools:create"}))
    book = DataConnections(store)
    made = book.create(
        actor,
        {
            "name": "warehouse",
            "engine": "postgres",
            "dsn": "postgresql://analyst:s3cret-pass@127.0.0.1:55432/analysis",
            "allowlist": {"schemas": ["public"], "tables": ["public.stores"]},
        },
    )
    assert "s3cret-pass" not in str(made)
    assert "dsn" not in made
    row = next(
        item
        for item in store.data_connections.values()
        if isinstance(item.get("dsn_ciphertext"), bytes) and item["dsn_ciphertext"]
    )
    assert b"s3cret-pass" not in row["dsn_ciphertext"]
    found_row = _find(store, {"connection": "warehouse", "_tenant_id": tenant})
    assert found_row is not None
    assert connection_dsn(store, found_row).startswith("postgresql://")
    rejected = dispatch_data(
        store,
        "query",
        {
            "connection": "warehouse",
            "_tenant_id": tenant,
            "sql": "DROP TABLE stores",
        },
    )
    assert rejected["code"] == "sql_rejected"
    missing = dispatch_data(
        store, "query", {"connection": "missing", "_tenant_id": tenant, "sql": "SELECT 1"}
    )
    assert missing["is_error"] is True


def test_spreadsheet_chart_and_export() -> None:
    store = demo_store()
    from ar_domain.tools.general import _prepare

    arguments: dict[str, object] = {
        "_run_id": uuid.uuid4(),
        "_tenant_id": uuid.uuid4(),
        "_user_id": uuid.uuid4(),
    }
    root = _prepare(store, arguments)
    (root / "workspace" / "inputs" / "walmart.csv").write_text(
        "state,stores\nTX,315\nFL,175\n", encoding="utf-8"
    )
    (root / "workspace" / "inputs" / "notes.tsv").write_text(
        "city\tcount\nAustin\t3\n", encoding="utf-8"
    )
    (root / "workspace" / "inputs" / "extra.json").write_text(
        '[{"sku":"paper","quantity":4}]', encoding="utf-8"
    )
    from ar_domain.tools.analysis import _xlsx

    (root / "workspace" / "inputs" / "book.xlsx").write_bytes(
        _xlsx(["sku", "quantity"], [["ink", 2]])
    )
    inspected = dispatch_general(store, "inspect_table", {**arguments, "path": "walmart.csv"})
    assert inspected["is_error"] is False
    assert "TX" in str(inspected["text"]) or "state" in str(inspected["text"])
    queried = dispatch_general(
        store,
        "query_table",
        {**arguments, "path": "walmart.csv", "sql": "SELECT state, stores FROM walmart"},
    )
    assert queried["is_error"] is False
    assert "315" in str(queried["text"])
    opened = dispatch_general(store, "inspect_table", {**arguments, "path": "inputs/book.xlsx"})
    assert opened["is_error"] is False
    dropped = dispatch_general(
        store, "query_table", {**arguments, "path": "walmart.csv", "sql": "DROP TABLE walmart"}
    )
    assert dropped["is_error"] is True
    exported = dispatch_general(
        store,
        "export_table",
        {**arguments, "format": "xlsx", "rows": [{"state": "TX", "stores": 315}]},
    )
    assert exported["is_error"] is False
    chart = dispatch_general(
        store,
        "chart",
        {
            **arguments,
            "kind": "bar",
            "title": "Stores",
            "xKey": "state",
            "yKey": "stores",
            "rows": [{"state": "TX", "stores": 315}, {"state": "FL", "stores": 175}],
        },
    )
    assert chart["is_error"] is False
    presentation = chart["structured"]["presentation"]
    assert presentation["kind"] == "chart"
    file_id = uuid.UUID(str(presentation["files"][0]["file_id"]))
    assert store.blobs[file_id].startswith(b"\x89PNG")
    for kind in ("line", "scatter", "pie"):
        drawn = dispatch_general(
            store, "chart", {**arguments, "kind": kind, "rows": [[kind, 2], ["b", 1]]}
        )
        assert drawn["is_error"] is False


def test_structured_output_retries_once() -> None:
    assert (
        validate_output('```json\n{"answer": 1}\n```', {"type": "object", "required": ["answer"]})
        is None
    )
    assert validate_output("not json", {"type": "object"})
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }
    assert output_schema({"output": {"jsonSchema": schema}}) == schema
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": ("Qwen/Qwen3-32B", {}, 5.0, True)  # type: ignore[method-assign]
    calls = {"n": 0}

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del messages, tools, tenant_id, model_alias
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "text": "There are 2992 stores.",
                "tool_calls": [],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            }
        return {
            "text": '{"answer":"There are 2992 stores."}',
            "tool_calls": [],
            "usage": {"tokens_in": 1, "tokens_out": 1},
        }

    store.complete_turn = complete  # type: ignore[method-assign]
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    for version in store.versions.values():
        definition = version.get("definition")
        if isinstance(definition, dict):
            definition["output"] = {"jsonSchema": schema}
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "How many?", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "How many?", []))
    run = store.runs[run_id]
    assert run["status"] == "completed"
    assert calls["n"] == 2
    reasons = [
        row.get("detail", {}).get("reason")
        for row in store.audit_log
        if row.get("action") == "run.retried"
    ]
    assert "structured_output" in reasons


def test_durable_connection_sql_is_issued() -> None:
    from ar_domain.durable.m23 import save_data_connections, save_service_connections

    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def execute(self, statement: object, params: dict[str, object] | None = None) -> None:
            self.calls.append((str(statement), params or {}))

    store = demo_store()
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    connection_id = uuid.uuid4()
    store.service_connections[connection_id] = {
        "id": connection_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "name": "proofapi",
        "kind": "bearer",
        "status": "active",
        "secret": b"sealed",
    }
    secret_id = uuid.uuid4()
    data_id = uuid.uuid4()
    store.secret_values[secret_id] = b"postgresql://analyst:s3cret-pass@127.0.0.1:55432/analysis"
    store.data_connections[data_id] = {
        "id": data_id,
        "tenant_id": tenant,
        "name": "warehouse",
        "engine": "postgres",
        "dsn_secret_ref_id": secret_id,
        "created_by": owner,
        "allowlist": {"tables": ["public.stores"]},
    }
    session = Session()
    asyncio.run(save_service_connections(session, [store.service_connections[connection_id]]))  # type: ignore[arg-type]
    asyncio.run(save_data_connections(session, store, [store.data_connections[data_id]]))  # type: ignore[arg-type]
    joined = "\n".join(sql for sql, _params in session.calls)
    assert "service_connections" in joined
    assert "data_connections" in joined
    params = [params for sql, params in session.calls if "dsn_ciphertext" in sql]
    assert params and b"s3cret-pass" not in params[0]["dsn_ciphertext"]  # type: ignore[index]


def test_memory_database_tools_and_mocked_drivers(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    args = {"connection": "Warehouse", "_tenant_id": tenant}
    assert dispatch_data(store, "list_schemas", args)["is_error"] is False
    assert "public.orders" in str(dispatch_data(store, "list_tables", args)["text"])
    described = dispatch_data(store, "describe_table", {**args, "table": "public.orders"})
    assert described["is_error"] is False
    denied = dispatch_data(store, "describe_table", {**args, "table": "secret.payroll"})
    assert denied["is_error"] is True
    counted = dispatch_data(store, "query", {**args, "sql": "SELECT count(*) FROM public.orders"})
    assert counted["is_error"] is False
    listed = dispatch_data(store, "query", {**args, "sql": "SELECT id FROM public.orders"})
    assert "paper" in str(listed["text"])
    assert dispatch_data(store, "nope", args)["code"] == "unknown_tool"

    class Cursor:
        def __init__(self) -> None:
            self.description = [type("Col", (), {"name": "n"})()]

        def fetchmany(self, _limit: int) -> list[tuple[int]]:
            return [(7,)]

    class Conn:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def execute(self, statement: str, _params: object = None) -> Cursor:
            self.calls.append(statement)
            if "BOOM" in statement:
                raise RuntimeError("password=s3cret-pass failed")
            return Cursor()

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    conn = Conn()
    monkeypatch.setattr("psycopg.connect", lambda *_a, **_k: conn)
    from ar_domain.tools.database import _execute

    found = _execute(
        "postgresql://analyst:s3cret-pass@127.0.0.1:55432/analysis",
        "postgres",
        "SELECT 1",
        timeout_s=5,
        limit=2,
    )
    assert found["rows"] == [[7]]
    assert any("READ ONLY" in item for item in conn.calls)
    with pytest.raises(SqlRejected, match=r"\*\*\*"):
        _execute(
            "postgresql://analyst:s3cret-pass@127.0.0.1:55432/analysis",
            "postgres",
            "SELECT BOOM",
            timeout_s=5,
            limit=1,
        )

    class MyCursor:
        def __init__(self) -> None:
            self.description = [("n",)]

        def execute(self, statement: str, _params: object = None) -> None:
            self.statement = statement

        def fetchmany(self, _limit: int) -> list[tuple[int]]:
            return [(3,)]

    class MyConn:
        def cursor(self) -> MyCursor:
            return MyCursor()

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr("pymysql.connect", lambda **_k: MyConn())
    mysql = _execute(
        "mysql://reader:pw@127.0.0.1:3306/app",
        "mysql",
        "SELECT 1",
        timeout_s=5,
        limit=2,
    )
    assert mysql["rows"] == [[3]]


def test_hydrate_round_trip_and_live_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from ar_domain.durable.m23 import (
        load_data_connections,
        load_model_catalog,
        load_service_connections,
    )
    from ar_domain.secrets.crypto import seal
    from ar_domain.tools.database import catalog, probe
    from ar_domain.tools.service_connections import connection_key

    tenant = uuid.uuid4()
    service_id = uuid.uuid4()
    data_id = uuid.uuid4()
    secret_id = uuid.uuid4()
    provider_id = uuid.uuid4()
    blob = seal(connection_key(), b"postgresql://analyst:pw@127.0.0.1:55432/analysis")

    class Result:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def mappings(self) -> Result:
            return self

        def __iter__(self) -> object:
            return iter(self._rows)

    class Session:
        async def execute(self, statement: object, _params: object = None) -> Result:
            sql = str(statement)
            if "FROM service_connections" in sql:
                return Result(
                    [
                        {
                            "id": service_id,
                            "tenant_id": tenant,
                            "name": "proofapi",
                            "secret": b"sealed",
                            "access_token": b"",
                            "refresh_token": b"",
                            "expires_at": None,
                        }
                    ]
                )
            if "FROM data_connections" in sql:
                return Result(
                    [
                        {
                            "id": data_id,
                            "tenant_id": tenant,
                            "name": "walmart",
                            "dsn_secret_ref_id": secret_id,
                            "dsn_ciphertext": blob,
                            "allowlist": {"tables": ["public.stores"]},
                            "schema_notes": "",
                        }
                    ]
                )
            if "FROM model_providers" in sql:
                return Result(
                    [
                        {
                            "id": provider_id,
                            "tenant_id": tenant,
                            "api_key_ref_id": uuid.uuid4(),
                            "base_url": "https://api.deepinfra.com/v1/openai",
                        }
                    ]
                )
            return Result([])

    store = demo_store()
    session = Session()
    asyncio.run(load_service_connections(session, store, tenant))  # type: ignore[arg-type]
    asyncio.run(load_data_connections(session, store, tenant))  # type: ignore[arg-type]
    assert store.service_connections[service_id]["name"] == "proofapi"
    assert store.secret_values[secret_id].startswith(b"postgresql://")
    store.durable_engine = create_async_engine("postgresql+asyncpg://unused@127.0.0.1/none")

    async def _read(_engine: object, _provider: uuid.UUID) -> str:
        return "loaded-key"

    monkeypatch.setattr("ar_domain.models.registry.read_api_key", _read)
    asyncio.run(load_model_catalog(session, store, tenant))  # type: ignore[arg-type]
    assert store.providers[provider_id]["api_key"] == "loaded-key"

    class Cursor:
        def __init__(self) -> None:
            self.description = [type("Col", (), {"name": "schema_name"})()]

        def fetchmany(self, _limit: int) -> list[tuple[str, str]]:
            return [("public", "stores")]

    class Conn:
        def execute(self, _statement: str, _params: object = None) -> Cursor:
            return Cursor()

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr("psycopg.connect", lambda *_a, **_k: Conn())
    row = store.data_connections[data_id]
    assert probe(store, row)["ok"] is True
    assert catalog(store, row)["tables"]
    listed = dispatch_data(store, "list_schemas", {"connection": "walmart", "_tenant_id": tenant})
    assert listed["is_error"] is False
    tables = dispatch_data(store, "list_tables", {"connection": "walmart", "_tenant_id": tenant})
    assert "public.stores" in str(tables["text"])
    detail = dispatch_data(
        store,
        "describe_table",
        {"connection": "walmart", "_tenant_id": tenant, "table": "public.stores"},
    )
    assert detail["is_error"] is False


def test_analysis_edges_and_output_schema() -> None:
    store = demo_store()
    from ar_domain.tools.general import _prepare

    arguments: dict[str, object] = {"_run_id": uuid.uuid4(), "_tenant_id": uuid.uuid4()}
    root = _prepare(store, arguments)
    (root / "workspace" / "inputs" / "extra.json").write_text(
        '{"rows": [{"sku": "paper", "n": 1}]}', encoding="utf-8"
    )
    missing = dispatch_general(store, "inspect_table", {**arguments, "path": "missing.csv"})
    assert missing["is_error"] is True
    assert dispatch_general(store, "query_table", arguments)["is_error"] is True
    assert dispatch_general(store, "export_table", arguments)["is_error"] is True
    exported = dispatch_general(
        store,
        "export_table",
        {**arguments, "path": "extra.json", "sql": "SELECT sku FROM extra", "format": "csv"},
    )
    assert exported["is_error"] is False
    assert dispatch_general(store, "chart", {**arguments, "kind": "other", "rows": []})["is_error"]
    assert validate_output("[1]", {"type": "object"})
    assert validate_output('{"answer": 1}', {"type": "object", "required": ["missing"]})
    assert output_schema({}) is None
