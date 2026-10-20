"""Seed and bootstrap decisions without a database."""

import asyncio
import uuid
from typing import Any

from ar_domain.identity.mail import send_email
from ar_domain.identity.seed import apply, ensure_admin, plan_limits
from ar_testing.factories import tenant_factory, user_factory
from ar_testing.tenancy import fill_path, paths_with_ids


class _Plan:
    id = uuid.uuid4()


class _Session:
    def __init__(self, *, plan_on_call: int | None = None) -> None:
        self.calls = 0
        self.plan_on_call = plan_on_call

    def add(self, row: object) -> None:
        del row

    async def flush(self) -> None:
        return None

    async def scalar(self, statement: object) -> object | None:
        del statement
        self.calls += 1
        if self.plan_on_call == self.calls:
            return _Plan()
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
    slug = asyncio.run(
        ensure_admin(
            _Session(plan_on_call=2),  # type: ignore[arg-type]
            slug="acme",
            name="Acme",
            email="a@b.c",
        )
    )
    assert tenant_id
    assert slug == "acme"


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
