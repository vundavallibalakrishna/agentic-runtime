"""Recorded AWS responses. No account and no live AWS call."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ar_domain.agents.access import Actor
from ar_domain.connectors.book import ConnectorBook
from ar_domain.connectors.dispatch import dispatch_connector
from ar_domain.identity.permissions import PERMISSION_KEYS

_INSTANCES = b"""<?xml version="1.0"?>
<DescribeInstancesResponse>
  <reservationSet><item>
    <instancesSet><item>
      <instanceId>i-recorded</instanceId>
      <instanceState><name>running</name></instanceState>
    </item></instancesSet>
  </item></reservationSet>
</DescribeInstancesResponse>
"""
_BUCKETS = b"""<?xml version="1.0"?>
<ListAllMyBucketsResult>
  <Buckets><Bucket><Name>recorded-bucket</Name></Bucket></Buckets>
</ListAllMyBucketsResult>
"""


def test_aws_reads_replay_a_local_xml_cassette() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            body = _INSTANCES
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            body = _BUCKETS
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            del fmt, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        from ar_testing.demo import demo_store  # noqa: PLC0415

        store = demo_store()
        actor = Actor(__import__("uuid").uuid4(), __import__("uuid").uuid4(), PERMISSION_KEYS)
        ConnectorBook(store).install(
            actor,
            "aws",
            {
                "connection_name": "aws",
                "secret": "recorded-secret",
                "username": "AKIARECORDED",
                "config": {"region": "us-east-1", "endpoint": base},
            },
        )
        args = {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id}
        listed = dispatch_connector(store, "aws_list_instances", args)
        assert listed["is_error"] is False, listed
        assert "i-recorded" in str(listed.get("structured"))
        buckets = dispatch_connector(store, "aws_list_buckets", args)
        assert buckets["is_error"] is False, buckets
        assert "recorded-bucket" in str(buckets.get("structured"))
    finally:
        server.shutdown()
