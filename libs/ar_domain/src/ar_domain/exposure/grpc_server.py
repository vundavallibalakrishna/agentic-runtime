# mypy: ignore-errors
"""gRPC server for A2A. JSON-RPC stays the fallback in ``grpc_a2a``.

The bearer token is the agent API key. A token from another tenant is not found.
Streaming methods yield the task, then any later events.
"""

from __future__ import annotations

import asyncio
from concurrent import futures
from typing import TYPE_CHECKING, Any

import grpc

from ar_domain.exposure import a2a
from ar_domain.exposure.a2a_gen import a2a_pb2, a2a_pb2_grpc
from ar_domain.exposure.keys import lookup

if TYPE_CHECKING:
    from collections.abc import Iterator


class A2AService(a2a_pb2_grpc.A2AServiceServicer):
    """Servicer that calls the same tasks as ``a2a.rpc``."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def SendMessage(
        self, request: a2a_pb2.SendMessageRequest, context: grpc.ServicerContext
    ) -> a2a_pb2.Task:
        key = self._key(context)
        self._same_tenant(key, request.tenant_id, context)
        params: dict[str, Any] = {
            "message": {"role": "user", "parts": [{"kind": "text", "text": request.text}]}
        }
        if request.context_id:
            params["message"]["context_id"] = request.context_id
        body = self._call(key, self._slug(key), "message/send", params, context)
        return _task(body, request.tenant_id)

    def SendStreamingMessage(
        self, request: a2a_pb2.SendMessageRequest, context: grpc.ServicerContext
    ) -> Iterator[a2a_pb2.StreamResponse]:
        task = self.SendMessage(request, context)
        yield a2a_pb2.StreamResponse(kind="task", task=task)

    def GetTask(
        self, request: a2a_pb2.GetTaskRequest, context: grpc.ServicerContext
    ) -> a2a_pb2.Task:
        key = self._key(context)
        self._same_tenant(key, request.tenant_id, context)
        body = self._call(key, self._slug(key), "tasks/get", {"id": request.id}, context)
        return _task(body, request.tenant_id)

    def ListTasks(
        self, request: a2a_pb2.ListTasksRequest, context: grpc.ServicerContext
    ) -> a2a_pb2.ListTasksResponse:
        key = self._key(context)
        self._same_tenant(key, request.tenant_id, context)
        body = self._call(
            key, self._slug(key), "tasks/list", {"pageSize": request.page_size or 20}, context
        )
        tasks = body.get("tasks") if isinstance(body, dict) else []
        rows = [_task(item, request.tenant_id) for item in tasks] if isinstance(tasks, list) else []
        return a2a_pb2.ListTasksResponse(tasks=rows)

    def CancelTask(
        self, request: a2a_pb2.GetTaskRequest, context: grpc.ServicerContext
    ) -> a2a_pb2.Task:
        key = self._key(context)
        self._same_tenant(key, request.tenant_id, context)
        body = self._call(key, self._slug(key), "tasks/cancel", {"id": request.id}, context)
        return _task(body, request.tenant_id)

    def TaskSubscription(
        self, request: a2a_pb2.GetTaskRequest, context: grpc.ServicerContext
    ) -> Iterator[a2a_pb2.StreamResponse]:
        yield from self._stream(request, context)

    def ResubscribeToTask(
        self, request: a2a_pb2.GetTaskRequest, context: grpc.ServicerContext
    ) -> Iterator[a2a_pb2.StreamResponse]:
        yield from self._stream(request, context)

    def _stream(
        self, request: a2a_pb2.GetTaskRequest, context: grpc.ServicerContext
    ) -> Iterator[a2a_pb2.StreamResponse]:
        key = self._key(context)
        self._same_tenant(key, request.tenant_id, context)
        body = self._call(
            key,
            self._slug(key),
            "tasks/resubscribe",
            {"id": request.id, "last_event_id": request.last_event_id},
            context,
        )
        task = _task(body, request.tenant_id)
        yield a2a_pb2.StreamResponse(kind="task", task=task)
        events = body.get("events") if isinstance(body, dict) else []
        if isinstance(events, list):
            for event in events:
                kind = str(event.get("kind") or "event") if isinstance(event, dict) else "event"
                yield a2a_pb2.StreamResponse(kind=kind, task=task)

    def _key(self, context: grpc.ServicerContext) -> dict[str, Any]:
        token = ""
        for item in context.invocation_metadata():
            if item.key.lower() == "authorization" and item.value.lower().startswith("bearer "):
                token = item.value.split(" ", 1)[1].strip()
        row, reason = lookup(self.store, token)
        if reason != "ok" or not isinstance(row, dict):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "bearer token is required")
            raise RuntimeError("bearer token is required")
        return row

    def _same_tenant(
        self, key: dict[str, Any], tenant_id: str, context: grpc.ServicerContext
    ) -> None:
        if not tenant_id or str(key.get("tenant_id")) != tenant_id:
            context.abort(grpc.StatusCode.NOT_FOUND, "not found")

    def _slug(self, key: dict[str, Any]) -> str:
        agents = getattr(self.store, "agents", {})
        agent = agents.get(key.get("agent_id")) if isinstance(agents, dict) else None
        if isinstance(agent, dict) and agent.get("slug"):
            return str(agent["slug"])
        return ""

    def _call(
        self,
        key: dict[str, Any],
        slug: str,
        method: str,
        params: dict[str, Any],
        context: grpc.ServicerContext,
    ) -> dict[str, Any]:
        result = asyncio.run(
            a2a.rpc(
                self.store,
                key,
                slug,
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            )
        )
        if "error" in result:
            error = result["error"] if isinstance(result["error"], dict) else {}
            context.abort(grpc.StatusCode.NOT_FOUND, str(error.get("message") or "not found"))
        body = result.get("result")
        return body if isinstance(body, dict) else {}


def serve(store: Any, host: str = "127.0.0.1", port: int = 0) -> tuple[grpc.Server, int]:
    """Start an insecure loopback server. Returns the server and the bound port."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    a2a_pb2_grpc.add_A2AServiceServicer_to_server(A2AService(store), server)
    bound = server.add_insecure_port(f"{host}:{port}")
    server.start()
    return server, bound


def _task(body: dict[str, Any], tenant_id: str) -> a2a_pb2.Task:
    status = body.get("status") if isinstance(body.get("status"), dict) else {}
    state = str(status.get("state") or "")
    text = ""
    message = status.get("message") if isinstance(status, dict) else None
    if isinstance(message, dict):
        parts = message.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and part.get("text"):
                    text = str(part["text"])
                    break
    return a2a_pb2.Task(
        id=str(body.get("id") or ""),
        tenant_id=tenant_id,
        state=state,
        text=text,
        resubscribed=bool(body.get("resubscribed")),
    )
