"""A2A over a real gRPC server. Proof: contract. JSON-RPC remains the fallback."""

from __future__ import annotations

import uuid

import grpc
import pytest

from ar_domain.chat.service import demo_id
from ar_domain.exposure import keys
from ar_domain.exposure.a2a_gen import a2a_pb2, a2a_pb2_grpc
from ar_domain.exposure.grpc_server import serve
from ar_testing.demo import demo_store


def _ready() -> tuple[object, str, str]:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    store.ensure_assistant(tenant, user)

    async def _answer(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        del text, names
        run = store.runs[run_id]
        run["status"] = "completed"
        assistant = store.messages[run["assistant_message_id"]]
        assistant["text"] = "hello from grpc"
        assistant["status"] = "completed"

    store.generate = _answer  # type: ignore[method-assign]
    agent = next(row for row in store.agents.values() if row.get("slug") == "assistant")
    _row, secret = keys.create_key(
        store, tenant_id=tenant, agent_id=agent["id"], user_id=user, label="stage12"
    )
    return store, secret, str(tenant)


def test_grpc_send_stream_resubscribe_and_tenant_scope() -> None:
    store, secret, tenant = _ready()
    server, port = serve(store)
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    stub = a2a_pb2_grpc.A2AServiceStub(channel)
    metadata = (("authorization", f"Bearer {secret}"),)
    try:
        sent = stub.SendMessage(
            a2a_pb2.SendMessageRequest(tenant_id=tenant, text="hello"),
            metadata=metadata,
        )
        assert sent.state == "completed"
        assert sent.text == "hello from grpc"
        streamed = list(
            stub.SendStreamingMessage(
                a2a_pb2.SendMessageRequest(tenant_id=tenant, text="again"),
                metadata=metadata,
            )
        )
        assert streamed[0].kind == "task"
        assert streamed[0].task.id
        again = list(
            stub.ResubscribeToTask(
                a2a_pb2.GetTaskRequest(tenant_id=tenant, id=sent.id),
                metadata=metadata,
            )
        )
        assert again[0].task.resubscribed is True
        listed = stub.ListTasks(a2a_pb2.ListTasksRequest(tenant_id=tenant), metadata=metadata)
        assert any(row.id == sent.id for row in listed.tasks)
        with pytest.raises(grpc.RpcError) as caught:
            stub.GetTask(
                a2a_pb2.GetTaskRequest(tenant_id=str(uuid.uuid4()), id=sent.id),
                metadata=metadata,
            )
        assert caught.value.code() == grpc.StatusCode.NOT_FOUND
    finally:
        channel.close()
        server.stop(None)


def test_grpc_rejects_a_missing_bearer() -> None:
    store, _secret, tenant = _ready()
    server, port = serve(store)
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    stub = a2a_pb2_grpc.A2AServiceStub(channel)
    with pytest.raises(grpc.RpcError) as missing:
        stub.SendMessage(a2a_pb2.SendMessageRequest(tenant_id=tenant, text="nope"))
    assert missing.value.code() == grpc.StatusCode.UNAUTHENTICATED
    channel.close()
    server.stop(None)
