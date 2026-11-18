#!/usr/bin/env python3
"""Sign OPA's bundle fetches and forward them to the API.

OPA's bundle client can send a static header. The install HMAC includes the
time and the path, so this process adds ``X-AR-Internal`` on each request.
The signature is the one in ``ar_common.internal_auth.sign_request``.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def sign(secret: str, method: str, path: str, now: int | None = None) -> str:
    """``<unix>.<hmac>`` over ``unix.METHOD.path``, matching internal_auth."""
    stamp = int(time.time()) if now is None else int(now)
    message = f"{stamp}.{method.upper()}.{path}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"{stamp}.{digest}"


class _Forward(BaseHTTPRequestHandler):
    def _serve(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        upstream = os.environ.get("AR_OPA_UPSTREAM", "").rstrip("/")
        if not upstream:
            self.send_error(500, "AR_OPA_UPSTREAM is not set")
            return
        path = urlsplit(self.path).path
        headers = {
            "X-AR-Internal": sign(os.environ.get("AR_INTERNAL_AUTH_SECRET", ""), self.command, path)
        }
        for name in ("Accept", "If-None-Match", "Content-Type"):
            value = self.headers.get(name)
            if value:
                headers[name] = value
        request = Request(  # noqa: S310 - the upstream is this install's API
            upstream + self.path,
            data=body,
            headers=headers,
            method=self.command,
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310
                payload = response.read()
                status = getattr(response, "status", 200)
                copied = {
                    key: response.headers[key]
                    for key in ("ETag", "Content-Type")
                    if key in response.headers
                }
        except HTTPError as exc:
            payload = exc.read()
            status = exc.code
            copied = {}
            if exc.headers is not None:
                for key in ("ETag", "Content-Type"):
                    value = exc.headers.get(key)
                    if value:
                        copied[key] = value
        except URLError:
            self.send_error(502, "the API did not answer")
            return
        self.send_response(status)
        for key, value in copied.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._serve()

    def do_POST(self) -> None:
        self._serve()

    def log_message(self, fmt: str, *args: object) -> None:
        del fmt, args


def serve() -> None:
    raw = os.environ.get("AR_OPA_FORWARD_URL", "http://127.0.0.1:9191")
    port = urlsplit(raw).port or 9191
    server = ThreadingHTTPServer(("127.0.0.1", port), _Forward)
    server.serve_forever()


def main() -> None:
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    command = [
        "opa",
        "run",
        "--server",
        "--addr",
        "0.0.0.0:8181",
        "--config-file",
        "/etc/opa/config.yaml",
    ]
    raise SystemExit(subprocess.call(command))  # noqa: S603


if __name__ == "__main__":
    main()
