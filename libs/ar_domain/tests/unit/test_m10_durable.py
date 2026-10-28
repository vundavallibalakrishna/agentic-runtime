"""Durable cutover helpers. Postgres round-trips live in the integration suite."""

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.durable.bind import should_bind
from ar_domain.durable.tracking import install_tracking


def test_should_bind_stays_off_under_pytest() -> None:
    assert should_bind() is False


def test_completion_url_prefers_the_gateway() -> None:
    service = ChatService()
    assert service.completion_url().endswith("/chat/completions")
    service.model_gateway_url = "http://gateway.test"
    assert service.completion_url() == "http://gateway.test/v1/chat/completions"
    service.model_gateway_url = "http://gateway.test/v1/"
    assert service.completion_url() == "http://gateway.test/v1/chat/completions"


def test_demo_id_is_stable() -> None:
    assert demo_id("tenant") == demo_id("tenant")
    assert demo_id("tenant") != demo_id("admin")


def test_tracking_marks_a_new_row_dirty() -> None:
    service = ChatService()
    install_tracking(service)
    skill_id = demo_id("skill")
    service.skills[skill_id] = {"id": skill_id, "slug": "status"}
    assert skill_id in service.skills.dirty  # type: ignore[attr-defined]
