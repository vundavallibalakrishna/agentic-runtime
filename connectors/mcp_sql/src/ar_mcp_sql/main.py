"""HTTP entrypoint for mcp-sql."""

import uvicorn
from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app
from ar_mcp_sql.server import handle

router = APIRouter()


class RpcBody(BaseModel):
    jsonrpc: str = "2.0"
    id: int = 1
    method: str
    params: dict[str, object] | None = None


class ProbeBody(BaseModel):
    sql: str = "SELECT 1"
    allow_tables: list[str] = ["public.orders"]


@router.post("/mcp")
async def mcp(body: RpcBody) -> dict[str, object]:
    payload = body.model_dump()
    return handle(payload)


@router.post("/internal/v1/connections:test")
async def probe(body: ProbeBody) -> dict[str, object]:
    """Reject anything the guard will not run. No database credentials are read."""
    outcome = handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "run_query", "arguments": {"sql": body.sql}},
        },
        allow_tables=set(body.allow_tables),
    )
    result = outcome.get("result")
    is_error = isinstance(result, dict) and result.get("isError") is True
    return {"ok": not is_error, "result": result}


LISTEN_PORT = 8010


class Settings(BaseServiceSettings):
    service_name: str = "mcp-sql"


def create_application() -> FastAPI:
    """Build the ASGI app."""
    app = create_app("mcp-sql", Settings())
    app.include_router(router)
    return app


def main() -> None:
    """Listen on ``AR_MCP_SQL_HOST_PORT`` (default 8010)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_MCP_SQL_HOST_PORT", LISTEN_PORT),
    )
