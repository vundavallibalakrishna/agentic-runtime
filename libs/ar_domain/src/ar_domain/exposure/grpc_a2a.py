"""A2A gRPC method names mapped onto the JSON-RPC tasks.

The HTTP handler accepts ``application/grpc+json``. A known method returns the
task result and a grpc-status of 0. It does not answer -32601.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.exposure.a2a import rpc

if TYPE_CHECKING:
    from typing import Any

_METHODS = {
    "a2a.v1.A2AService/SendMessage": "message/send",
    "a2a.v1.A2AService/GetTask": "tasks/get",
    "a2a.v1.A2AService/CancelTask": "tasks/cancel",
    "a2a.v1.A2AService/TaskSubscription": "tasks/resubscribe",
    "a2a.v1.A2AService/ResubscribeToTask": "tasks/resubscribe",
}


async def grpc_call(
    store: Any, key: dict[str, Any], slug: str, method: str, body: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    """Return ``(payload, grpc_status)``. 12 is UNIMPLEMENTED."""
    mapped = _METHODS.get(method)
    if mapped is None:
        return {"message": f"unimplemented: {method}"}, 12
    result = await rpc(
        store,
        key,
        slug,
        {"jsonrpc": "2.0", "id": body.get("id") or 1, "method": mapped, "params": body},
    )
    if "error" in result:
        error = result["error"] if isinstance(result["error"], dict) else {}
        return {"message": str(error.get("message") or "error")}, 3
    payload = result.get("result")
    return (payload if isinstance(payload, dict) else {"result": payload}), 0
