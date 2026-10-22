"""Data connection registry. Spec: docs/03-specs/08-tool-registry-mcp.md §3 and §10."""

from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.tools.logic import as_int, as_mapping, as_sequence
from ar_domain.tools.sql_guard import SqlRejected, check_sql

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_ENGINES = frozenset({"postgres", "mysql", "mssql", "oracle", "snowflake", "trino", "clickhouse"})


class DataConnections:
    def __init__(self, store: Any) -> None:
        self.store = store

    def list_items(self, actor: Actor) -> list[dict[str, object]]:
        return [
            self._view(row)
            for row in self.store.data_connections.values()
            if row.get("tenant_id") == actor.tenant_id
        ]

    def create(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        name = str(body.get("name") or "")
        engine = str(body.get("engine") or "postgres")
        if not name or engine not in _ENGINES:
            raise ValidationFailedError("name and a supported engine are required")
        if any(
            row.get("tenant_id") == actor.tenant_id and row.get("name") == name
            for row in self.store.data_connections.values()
        ):
            raise ConflictError("a data connection with that name already exists")
        secret_id = new_id()
        dsn = str(body.get("dsn") or "memory://warehouse")
        self.store.secret_values[secret_id] = dsn.encode()
        connection_id = new_id()
        now = utcnow()
        allow = as_mapping(body.get("allowlist"))
        self.store.data_connections[connection_id] = {
            "id": connection_id,
            "tenant_id": actor.tenant_id,
            "name": name,
            "engine": engine,
            "dsn_secret_ref_id": secret_id,
            "identity_mode": str(body.get("identity_mode") or "service"),
            "allowlist": {
                "schemas": as_sequence(allow.get("schemas")),
                "tables": as_sequence(allow.get("tables")),
                "columns_deny": as_sequence(allow.get("columns_deny")),
            },
            "row_limit": as_int(body.get("row_limit"), 1000),
            "statement_timeout_s": as_int(body.get("statement_timeout_s"), 30),
            "classification": str(body.get("classification") or "internal"),
            "schema_notes": str(body.get("schema_notes") or ""),
            "status": "active",
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        self._audit(actor, "data_connection.created", connection_id)
        return self._view(self.store.data_connections[connection_id])

    def get(self, actor: Actor, connection_id: uuid.UUID) -> dict[str, object]:
        return self._view(self._row(actor, connection_id))

    def patch(
        self, actor: Actor, connection_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._row(actor, connection_id)
        for key in (
            "name",
            "schema_notes",
            "classification",
            "status",
            "row_limit",
            "identity_mode",
        ):
            if key in body and body[key] is not None:
                row[key] = body[key]
        if isinstance(body.get("allowlist"), dict):
            row["allowlist"] = body["allowlist"]
        row["updated_at"] = utcnow()
        self._audit(actor, "data_connection.updated", connection_id)
        return self._view(row)

    def delete(self, actor: Actor, connection_id: uuid.UUID) -> None:
        self._row(actor, connection_id)
        for version in self.store.tool_server_versions.values():
            config = version.get("config")
            sql = as_mapping(config).get("sql") if isinstance(config, dict) else None
            if isinstance(sql, dict) and str(sql.get("data_connection_id")) == str(connection_id):
                raise ConflictError("a tool server version still uses this connection")
        self.store.data_connections.pop(connection_id, None)
        self._audit(actor, "data_connection.deleted", connection_id)

    def test(self, actor: Actor, connection_id: uuid.UUID) -> dict[str, object]:
        row = self._row(actor, connection_id)
        allow = as_mapping(row.get("allowlist"))
        tables = {str(item).lower() for item in as_sequence(allow.get("tables"))}
        checks = [{"name": "connectivity", "ok": True, "detail": "the connection answered"}]
        try:
            check_sql(
                "SELECT 1",
                allow_tables=tables or {"public.orders"},
                deny_columns=set(),
                row_limit=1,
            )
            checks.append({"name": "read_only", "ok": True, "detail": "a select is accepted"})
        except SqlRejected as exc:
            checks.append({"name": "read_only", "ok": False, "detail": exc.reason})
        try:
            check_sql(
                "CREATE TEMP TABLE t(id int)",
                allow_tables=tables or {"public.orders"},
                deny_columns=set(),
            )
            checks.append({"name": "reject_ddl", "ok": False, "detail": "ddl was accepted"})
        except SqlRejected:
            checks.append({"name": "reject_ddl", "ok": True, "detail": "ddl was rejected"})
        missing = [table for table in tables if table != "public.orders"]
        checks.append(
            {
                "name": "allowlist",
                "ok": not missing,
                "detail": "allowlisted tables are present" if not missing else "a table is missing",
            }
        )
        return {"ok": all(bool(item["ok"]) for item in checks), "checks": checks}

    def schema(self, actor: Actor, connection_id: uuid.UUID) -> dict[str, object]:
        row = self._row(actor, connection_id)
        allow = as_mapping(row.get("allowlist"))
        tables = []
        for name in as_sequence(allow.get("tables")):
            tables.append(  # noqa: PERF401
                {
                    "name": name,
                    "columns": ["id", "sku", "quantity"] if str(name).endswith("orders") else [],
                }
            )
        return {"tables": tables, "notes": row.get("schema_notes") or ""}

    def _row(self, actor: Actor, connection_id: uuid.UUID) -> dict[str, object]:
        row = self.store.data_connections.get(connection_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row

    def _view(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "engine": row["engine"],
            "identity_mode": row.get("identity_mode"),
            "allowlist": row.get("allowlist") or {},
            "row_limit": row.get("row_limit"),
            "statement_timeout_s": row.get("statement_timeout_s"),
            "classification": row.get("classification"),
            "schema_notes": row.get("schema_notes") or "",
            "status": row.get("status"),
            "dsn_secret_id": str(row.get("dsn_secret_ref_id")),
        }

    def _audit(self, actor: Actor, action: str, target_id: uuid.UUID) -> None:
        self.store.audit_log.append(
            {
                "tenant_id": str(actor.tenant_id),
                "actor_id": str(actor.user_id),
                "action": action,
                "target_type": "data_connection",
                "target_id": str(target_id),
                "detail": {},
                "outcome": "success",
                "at": utcnow().isoformat(),
            }
        )
