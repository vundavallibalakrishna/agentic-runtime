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

# Say "no database" before the application reads its settings.
os.environ["AR_DURABLE_STATE"] = "memory"
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
from ar_common.host_ports import listen_port
from ar_testing.demo import serve_demo_tenant, start_session
from ar_testing.demo_people import catalogue

SIGN_IN_PATH = "/api/v1/test/sign-in"


class DemoSignIn:
    """Answer the test sign-in path and pass every other request to the product."""

    def __init__(self, app: ASGIApp, product: object) -> None:
        self.app = app
        self.product = product

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] == SIGN_IN_PATH:
            response = await self._sign_in(Request(scope, receive))
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

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
    """The product application over the demo tenant, behind the test sign-in."""
    app = serve_demo_tenant(create_application())
    return DemoSignIn(app, app)


def main() -> None:
    """Listen on ``AR_PORT``."""
    uvicorn.run(build(), host="127.0.0.1", port=listen_port("AR_PORT", LISTEN_PORT))


if __name__ == "__main__":
    main()
