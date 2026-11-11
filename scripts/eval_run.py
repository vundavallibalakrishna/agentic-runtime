#!/usr/bin/env python
"""Eval gym contract check against a local OpenAI-compatible stub.

The report has an empty model id. It is not a live run. A live eval is an eval run in
the product: ``scripts/certify_live.sh`` starts one from ``evals/live/certification.yaml``.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import orjson
import yaml

from ar_domain.evals.harness import case_passed, regressed, stub_reply, summarise
from ar_domain.models.request import (
    bound_max_tokens,
    chat_completion_body,
    redact_provider_error,
)

ROOT = Path(__file__).resolve().parents[1]
ASSISTANT = ROOT / "evals" / "gym" / "assistant" / "cases.yaml"
REDTEAM = ROOT / "evals" / "gym" / "redteam" / "cases.yaml"
BASELINE = ROOT / "evals" / "baseline.json"


def load_cases() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in (ASSISTANT, REDTEAM):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            rows.extend(item for item in loaded if isinstance(item, dict))
    return rows


class _Stub(BaseHTTPRequestHandler):
    cases: dict[str, dict[str, object]]

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            body = orjson.loads(raw)
        except orjson.JSONDecodeError:
            body = {}
        case_id = ""
        messages = body.get("messages") if isinstance(body, dict) else None
        if isinstance(messages, list):
            for message in messages:
                if isinstance(message, dict) and message.get("role") == "user":
                    case_id = str(message.get("content") or "").split("\n", 1)[0]
                    break
        case = self.cases.get(case_id, {})
        reply = stub_reply(case)
        tool = str(reply.get("tool") or "")
        message: dict[str, object] = {"role": "assistant", "content": reply["text"]}
        if tool:
            message["tool_calls"] = [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": tool, "arguments": "{}"},
                }
            ]
        payload = {
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 8},
        }
        encoded = orjson.dumps(payload)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt: str, *args: object) -> None:
        del fmt, args


def _serve(cases: list[dict[str, object]]) -> tuple[ThreadingHTTPServer, str]:
    _Stub.cases = {str(case.get("id") or ""): case for case in cases}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}/v1/chat/completions"


def _case_max_tokens(case: dict[str, object]) -> int:
    raw = case.get("max_tokens", case.get("maxTokens"))
    return bound_max_tokens(raw)


def _post(url: str, case: dict[str, object]) -> dict[str, object]:
    prompt = str(case.get("prompt") or "")
    content = f"{case.get('id')}\n{prompt}"
    body = chat_completion_body(
        model=os.environ.get("AR_LLM_MODEL", "stub"),
        messages=[{"role": "user", "content": content}],
        max_tokens=_case_max_tokens(case),
    )
    data = orjson.dumps(body)
    headers = {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")  # noqa: S310
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            raw = response.read()
            status = getattr(response, "status", 200)
            payload = orjson.loads(raw)
    except urllib.error.HTTPError as exc:
        latency = (time.perf_counter() - started) * 1000
        detail = b""
        reader = getattr(exc, "read", None)
        if callable(reader):
            try:
                detail = reader()
            except Exception:  # noqa: BLE001 - the status is the record that matters
                detail = b""
        return {
            "text": "",
            "tool": "",
            "tokens": 0,
            "latency_ms": latency,
            "error": "HTTPError",
            "status": exc.code,
            "provider_error": redact_provider_error(detail or str(exc.reason or "").encode()),
        }
    except urllib.error.URLError as exc:
        latency = (time.perf_counter() - started) * 1000
        return {
            "text": "",
            "tool": "",
            "tokens": 0,
            "latency_ms": latency,
            "error": type(exc).__name__,
            "status": None,
            "provider_error": redact_provider_error(str(getattr(exc, "reason", exc))),
        }
    latency = (time.perf_counter() - started) * 1000
    message = {}
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        raw = choices[0].get("message")
        message = raw if isinstance(raw, dict) else {}
    tool = ""
    calls = message.get("tool_calls")
    if isinstance(calls, list) and calls and isinstance(calls[0], dict):
        function = calls[0].get("function")
        if isinstance(function, dict):
            tool = str(function.get("name") or "")
    usage = payload.get("usage") if isinstance(payload, dict) else {}
    tokens = 0
    if isinstance(usage, dict):
        tokens = int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
    return {
        "text": str(message.get("content") or ""),
        "tool": tool,
        "tokens": tokens,
        "latency_ms": latency,
        "cost_micros": 0,
        "status": status,
        "error": "",
        "provider_error": "",
    }


def run() -> dict[str, object]:
    cases = load_cases()
    server, url = _serve(cases)
    results: list[dict[str, object]] = []
    try:
        for case in cases:
            reply = _post(url, case)
            scored = case_passed(case, reply)
            scored["latency_ms"] = reply.get("latency_ms")
            scored["tokens"] = reply.get("tokens")
            scored["cost_micros"] = reply.get("cost_micros")
            scored["error"] = bool(reply.get("error"))
            scored["status"] = reply.get("status")
            scored["provider_error"] = reply.get("provider_error") or ""
            scored["id"] = case.get("id")
            results.append(scored)
    finally:
        server.shutdown()
    summary = summarise(results)
    summary["errors"] = float(sum(1 for row in results if row.get("error")))
    return {
        "label": "contract",
        "modelId": "",
        "date": time.strftime("%Y-%m-%d", time.gmtime()),
        "cases": len(results),
        "summary": summary,
        "results": [
            {
                "id": row.get("id"),
                "pass": row.get("pass"),
                "latency_ms": row.get("latency_ms"),
                "status": row.get("status"),
                "error": row.get("error"),
                "provider_error": row.get("provider_error") or "",
            }
            for row in results
        ],
    }


def main() -> int:
    check = "--check" in sys.argv
    report = run()
    print(json.dumps(report, indent=2))
    if not check:
        return 0
    baseline = orjson.loads(BASELINE.read_bytes())
    current = report["summary"]
    expected = baseline.get("summary") if isinstance(baseline, dict) else {}
    if not isinstance(current, dict) or not isinstance(expected, dict):
        print("baseline is missing a summary", file=sys.stderr)
        return 1
    worse = regressed(current, expected)
    if worse:
        print("eval regressed: " + ", ".join(worse), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
