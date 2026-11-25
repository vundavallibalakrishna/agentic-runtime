"""The API process the browser tests run against.

It is the product's own application, started with no database and given the demo tenant:
its people, agents, fixtures and example conversations. The demo tenant is test data, so
it is put in from here. A product process never creates it, and one that cannot reach its
database is not ready.

The browser tests also sign in here. ``/api/v1/test/sign-in`` exists only in this
harness: it starts a session for one of the demo tenant's people and sends the browser to
the workspace. The product has no such door.

    uv run python services/api/tests/support/e2e_server.py
"""

import os
import time

# Say "no database" before the application reads its settings.
os.environ["AR_DURABLE_STATE"] = "memory"
# No collector runs beside the browser tests. An export to localhost wedges the API.
os.environ["AR_OTEL_EXPORTER_OTLP_ENDPOINT"] = "off"
# The stand-in model server and the fixture pages are on this machine's own addresses.
os.environ.setdefault("AR_EGRESS_ALLOW_LOOPBACK", "true")
os.environ.setdefault("AR_EGRESS_ALLOW_WILDCARD", "true")
os.environ.setdefault("AR_SANDBOX_ALLOW_UNISOLATED", "true")
os.environ.setdefault("AR_FILES_SCANNER", "none")

import uvicorn
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from ar_api.main import LISTEN_PORT, create_application
from ar_common.host_ports import api_listen_port
from ar_testing.demo import rebuild_demo_store, serve_demo_tenant, start_session
from ar_testing.demo_people import catalogue

SIGN_IN_PATH = "/api/v1/test/sign-in"
RESET_PATH = "/api/v1/test/reset"
TRAFFIC_PATH = "/api/v1/test/traffic"
REVIEW_PATH = "/api/v1/test/review-link"
REVIEW_RESULT_PATH = "/api/v1/test/review-result"
# Probes the harness and the product do not bill to a person.
_UNCOUNTED = frozenset(
    {
        "/healthz",
        "/readyz",
        "/metrics",
        SIGN_IN_PATH,
        RESET_PATH,
        TRAFFIC_PATH,
        REVIEW_PATH,
        REVIEW_RESULT_PATH,
    }
)
_WINDOW_S = 60.0


class RequestTraffic:
    """Timestamps of product requests, so a browser walk can be checked against the limit."""

    def __init__(self) -> None:
        self._hits: list[tuple[float, str]] = []

    def reset(self) -> None:
        self._hits.clear()

    def record(self, path: str) -> None:
        self._hits.append((time.time(), path))

    def snapshot(self) -> dict[str, object]:
        moments = [moment for moment, _path in self._hits]
        counts: dict[str, int] = {}
        for _moment, path in self._hits:
            counts[path] = counts.get(path, 0) + 1
        top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]
        return {
            "total": len(self._hits),
            "peakPerMinute": peak_per_minute(moments),
            "windowSeconds": int(_WINDOW_S),
            "sessionChecks": counts.get("/api/v1/auth/session", 0),
            "topPaths": [{"path": path, "count": count} for path, count in top],
        }


def peak_per_minute(moments: list[float], window_s: float = _WINDOW_S) -> int:
    """The most requests in any sliding window. Empty is zero."""
    if not moments:
        return 0
    ordered = sorted(moments)
    peak = 1
    start = 0
    for end, moment in enumerate(ordered):
        while ordered[start] <= moment - window_s:
            start += 1
        peak = max(peak, end - start + 1)
    return peak


class DemoSignIn:
    """Answer the test sign-in and reset paths and pass every other request to the product."""

    def __init__(self, app: ASGIApp, product: object) -> None:
        self.app = app
        self.product = product
        self.traffic = RequestTraffic()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == SIGN_IN_PATH:
            response = await self._sign_in(Request(scope, receive))
            await response(scope, receive, send)
            return
        if scope["type"] == "http" and scope["path"] == RESET_PATH:
            # The tests call this between a failed attempt and its retry, so the retry starts
            # from the seeded demo tenant and not from the rows the attempt before it left.
            rebuild_demo_store(self.product)
            await JSONResponse({"reset": True})(scope, receive, send)
            return
        if scope["type"] == "http" and scope["path"] == REVIEW_RESULT_PATH:
            await self._review_result()(scope, receive, send)
            return
        if scope["type"] == "http" and scope["path"] == REVIEW_PATH:
            await self._review_link()(scope, receive, send)
            return
        if scope["type"] == "http" and scope["path"] == TRAFFIC_PATH:
            response = self._traffic(Request(scope, receive))
            await response(scope, receive, send)
            return
        if scope["type"] == "http" and scope["path"] not in _UNCOUNTED:
            self.traffic.record(str(scope["path"]))
        await self.app(scope, receive, send)

    def _review_link(self) -> JSONResponse:
        """One pending approval whose argument spelling the browser must not rename."""
        import uuid

        from ar_domain.approvals.review_link import issue_review_token, link_deadline
        from ar_domain.approvals.service import ApprovalBook
        from ar_domain.chat.service import demo_id

        store = self.product.state.chat
        tenant = demo_id("tenant")
        user = demo_id("admin")
        run_id = uuid.uuid4()
        store.runs[run_id] = {
            "id": run_id,
            "tenant_id": tenant,
            "user_id": user,
            "status": "waiting_approval",
            "conversation_id": None,
        }
        row = ApprovalBook(store).create_pending(
            tenant_id=tenant,
            user_id=user,
            run_id=run_id,
            agent_id=None,
            tool_call_id=uuid.uuid4(),
            qualified_name="pack.example",
            risk_class="W2",
            args_hash="hash-1",
            arguments={"target_date": "2026-01-02"},
            requirement={"approvers": {"mode": "requester"}, "ttl_s": 3600},
            reasons=["ask"],
            preview={"title": "Send", "summary": "Round trip"},
        )
        token = issue_review_token(row["id"], tenant, user, link_deadline(row["expires_at"]))
        return JSONResponse({"token": token, "approvalId": str(row["id"])})

    def _review_result(self) -> JSONResponse:
        rows = [
            row
            for row in self.product.state.chat.approvals.values()
            if isinstance(row, dict) and row.get("status") == "pending"
        ]
        rows.sort(key=lambda item: str(item.get("created_at") or ""))
        latest = rows[-1] if rows else {}
        arguments = latest.get("arguments") if isinstance(latest.get("arguments"), dict) else {}
        return JSONResponse({"arguments": arguments})

    def _traffic(self, request: Request) -> Response:
        if request.method == "POST":
            self.traffic.reset()
            return JSONResponse({"reset": True})
        return JSONResponse(self.traffic.snapshot())

    async def _sign_in(self, request: Request) -> Response:
        email = (request.query_params.get("email") or await _posted_email(request)).strip().lower()
        if email not in catalogue():
            return JSONResponse({"error": "not a person of the demo tenant"}, status_code=404)
        cookies = await start_session(self.product, email)
        response = RedirectResponse("/chat", status_code=303)
        response.set_cookie(
            "ar_session", cookies["ar_session"], httponly=True, samesite="lax", secure=False
        )
        response.set_cookie(
            "ar_csrf", cookies["ar_csrf"], httponly=False, samesite="lax", secure=False
        )
        return response


async def _posted_email(request: Request) -> str:
    if request.method != "POST":
        return ""
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        return str(body.get("email") or "") if isinstance(body, dict) else ""
    form = await request.form()
    return str(form.get("email") or "")


def build() -> ASGIApp:
    """The product application over the demo tenant, behind the test sign-in.

    The rate limit stays the product's own 600 requests a minute. A browser walk has to fit.
    """
    app = serve_demo_tenant(create_application())
    return DemoSignIn(app, app)


def main() -> None:
    """Listen on ``AR_PORT``. Turns run on the test Temporal server."""
    from ar_testing.runtime import boot_test_runtime

    bridge = boot_test_runtime()
    app = build()
    settings = app.product.state.settings
    settings.temporal_address = bridge.address
    settings.temporal_namespace = bridge.namespace
    uvicorn.run(app, host="127.0.0.1", port=api_listen_port(LISTEN_PORT))


if __name__ == "__main__":
    main()
