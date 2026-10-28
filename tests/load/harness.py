"""Short platform-overhead probe used by the load report and unit tests."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from statistics import quantiles
from time import perf_counter
from urllib.request import urlopen

BUDGETS_MS = {
    "simple_get": 100,
    "post_message": 150,
    "tool_overhead": 50,
    "policy": 10,
    "quota": 2,
    "sse_fanout": 100,
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length") or 0)
        if length:
            self.rfile.read(length)
        body = b'{"run":{"id":"load"}}'
        self.send_response(202)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        del fmt, args


def percentile(samples: list[float], fraction: float) -> float:
    """Nearest-rank percentile in milliseconds."""
    if not samples:
        raise ValueError("no samples")
    if len(samples) < 2:
        return samples[0] * 1000
    ranks = quantiles(samples, n=100, method="inclusive")
    index = min(len(ranks) - 1, max(0, int(fraction * 100) - 1))
    return ranks[index] * 1000


def run_probe(*, requests: int = 40) -> dict[str, float]:
    """Hit an in-process server and return p95 milliseconds per path."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    try:
        gets = [_time_request(f"{base}/healthz") for _ in range(requests)]
        posts = [
            _time_request(f"{base}/api/v1/conversations/demo/messages", method="POST")
            for _ in range(requests)
        ]
    finally:
        server.shutdown()
        thread.join(timeout=2)
    return {
        "simple_get_p95_ms": percentile(gets, 0.95),
        "post_message_p95_ms": percentile(posts, 0.95),
    }


def _time_request(url: str, method: str = "GET") -> float:
    started = perf_counter()
    request_body = b"{}" if method == "POST" else None
    with urlopen(url, data=request_body, timeout=2) as response:  # noqa: S310
        response.read()
    return perf_counter() - started
