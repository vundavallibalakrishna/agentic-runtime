"""Suspending a person through the API: they are shut out at once, and can be let back in."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from ar_testing.demo import demo_application

MEMBER = "member@dev.local"


def _signed_in(app: Any, email: str) -> TestClient:
    client = TestClient(app)
    signed = client.post("/api/v1/auth/login", json={"email": email, "password": "dev-password"})
    assert signed.status_code == 200, signed.text
    # What the page sends with a change: the token from its cookie, and where it is from.
    client.headers.update(
        {
            "x-csrf-token": str(client.cookies.get("ar_csrf") or ""),
            "origin": str(app.state.settings.public_url),
        }
    )
    return client


def _people(admin: TestClient) -> dict[str, dict[str, Any]]:
    return {row["email"]: row for row in admin.get("/api/v1/users").json()["items"]}


def test_a_suspended_person_is_shut_out_and_can_be_let_back_in() -> None:
    app = demo_application()
    admin = _signed_in(app, "admin@dev.local")
    member = _signed_in(app, MEMBER)
    assert member.get("/api/v1/me").status_code == 200
    person = _people(admin)[MEMBER]
    assert person["status"] == "active"

    suspended = admin.patch(f"/api/v1/users/{person['id']}", json={"status": "suspended"})
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended"
    assert _people(admin)[MEMBER]["status"] == "suspended"
    # The session they already had stops working, and they cannot start another.
    assert member.get("/api/v1/me").status_code in {401, 403}
    again = TestClient(app).post(
        "/api/v1/auth/login", json={"email": MEMBER, "password": "dev-password"}
    )
    assert again.status_code in {401, 403}

    back = admin.patch(f"/api/v1/users/{person['id']}", json={"status": "active"})
    assert back.status_code == 200
    assert _people(admin)[MEMBER]["status"] == "active"
    assert _signed_in(app, MEMBER).get("/api/v1/me").status_code == 200


def test_nobody_suspends_their_own_account() -> None:
    app = demo_application()
    admin = _signed_in(app, "admin@dev.local")
    me = _people(admin)["admin@dev.local"]
    refused = admin.patch(f"/api/v1/users/{me['id']}", json={"status": "suspended"})
    assert refused.status_code == 422
    assert "your own account" in refused.text
    assert admin.get("/api/v1/me").status_code == 200


def test_a_person_who_may_not_manage_users_cannot_suspend() -> None:
    app = demo_application()
    admin = _signed_in(app, "admin@dev.local")
    member = _signed_in(app, MEMBER)
    target = _people(admin)["builder@dev.local"]
    refused = member.patch(f"/api/v1/users/{target['id']}", json={"status": "suspended"})
    assert refused.status_code == 403
    assert _people(admin)["builder@dev.local"]["status"] == "active"
