"""Seed and bootstrap decisions without a database."""

import asyncio
import uuid
from typing import Any

import pytest

from ar_domain.identity.mail import send_email
from ar_domain.identity.seed import apply, ensure_admin, plan_limits
from ar_testing.factories import tenant_factory, user_factory
from ar_testing.tenancy import fill_path, paths_with_ids


class _Row:
    id = uuid.uuid4()


class _Session:
    """Answers ``scalar`` with a row on the listed calls and with nothing on the others."""

    def __init__(self, *, found_on_calls: frozenset[int] = frozenset()) -> None:
        self.calls = 0
        self.found_on_calls = found_on_calls
        self.added: list[object] = []

    def add(self, row: object) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None

    async def scalar(self, statement: object) -> object | None:
        del statement
        self.calls += 1
        if self.calls in self.found_on_calls:
            return _Row()
        return None


def test_plan_limits_cover_each_catalogue_key() -> None:
    free = plan_limits("free")
    team = plan_limits("team")
    hosted = plan_limits("self_hosted")
    enterprise = plan_limits("enterprise")
    assert free["max_users"] == 5
    assert team["max_users"] == 50
    assert hosted["max_users"] is None
    assert "max_users" in enterprise


def test_seed_inserts_when_the_catalogue_is_empty() -> None:
    session = _Session()
    tenant_id = asyncio.run(apply(session))  # type: ignore[arg-type]
    assert tenant_id


def test_ensure_admin_adds_the_tenant_the_person_and_the_admin_role() -> None:
    # Calls: tenant (missing), plan (found), user (missing), role (found), assignment (missing).
    session = _Session(found_on_calls=frozenset({2, 4}))
    slug = asyncio.run(
        ensure_admin(
            session,  # type: ignore[arg-type]
            slug="acme",
            name="Acme",
            email="Ada@Acme.Example",
            display_name="Ada Lovelace",
        )
    )
    assert slug == "acme"
    kinds = [type(row).__name__ for row in session.added]
    assert kinds == ["Tenant", "User", "RoleAssignment"]
    user = session.added[1]
    assert user.email == "ada@acme.example"  # type: ignore[attr-defined]
    assert user.display_name == "Ada Lovelace"  # type: ignore[attr-defined]


def test_ensure_admin_refuses_an_install_without_the_catalogue() -> None:
    """An admin without the admin role is a broken install, so nothing is half-made."""
    with pytest.raises(RuntimeError, match="self_hosted"):
        asyncio.run(
            ensure_admin(_Session(), slug="acme", name="Acme", email="a@b.c")  # type: ignore[arg-type]
        )
    with pytest.raises(RuntimeError, match="tenant_admin"):
        asyncio.run(
            ensure_admin(
                _Session(found_on_calls=frozenset({2})),  # type: ignore[arg-type]
                slug="acme",
                name="Acme",
                email="a@b.c",
            )
        )


def test_factories_and_path_helper() -> None:
    user = user_factory(email="a@b.c")
    tenant = tenant_factory(slug="acme")
    assert user["email"] == "a@b.c"
    assert tenant["slug"] == "acme"
    paths = paths_with_ids({"paths": {"/users/{user_id}": {}, "/meta": {}, "nope": 1}})
    assert paths == ["/users/{user_id}"]
    assert fill_path("/users/{user_id}", user_id="u1") == "/users/u1"
    assert paths_with_ids({}) == []


def test_send_email_uses_the_smtp_client(monkeypatch: Any) -> None:
    sent: list[object] = []

    class _Client:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            del host, port, timeout

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def starttls(self) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            del username, password

        def send_message(self, message: object) -> None:
            sent.append(message)

    monkeypatch.setattr("ar_domain.identity.mail.smtplib.SMTP", _Client)
    send_email(
        host="localhost",
        port=1025,
        sender="from@dev.local",
        recipient="to@dev.local",
        subject="hi",
        body="body",
        username="mail",
        password="mail",  # noqa: S106
        starttls=True,
    )
    assert sent
