"""Host ports stay aligned with localhost URLs."""

from pathlib import Path
from typing import TYPE_CHECKING

from ar_common.host_ports import (
    PortCheck,
    _published_ports,
    align_local_value,
    apply_host_ports,
    fake_llm_base_url,
    health_urls,
    listen_port,
    port_in_use,
    prepare_env_file,
    rewrite_local_port,
)
from ar_common.settings import BaseServiceSettings

if TYPE_CHECKING:
    import pytest


def test_rewrite_replaces_localhost_port_and_keeps_credentials() -> None:
    url = "postgresql+asyncpg://ar_app:ar_app@localhost:5432/agentic_runtime"
    assert rewrite_local_port(url, 15432) == (
        "postgresql+asyncpg://ar_app:ar_app@localhost:15432/agentic_runtime"
    )
    assert rewrite_local_port("redis://127.0.0.1:6379/0", 16379) == "redis://127.0.0.1:16379/0"
    assert rewrite_local_port("localhost:7233", 17233) == "localhost:17233"


def test_rewrite_leaves_remote_hosts() -> None:
    remote = "postgresql+asyncpg://ar_app:ar_app@postgres:5432/agentic_runtime"
    assert rewrite_local_port(remote, 15432) == remote


def test_default_port_resets_a_localhost_url() -> None:
    custom = "postgresql+asyncpg://ar_app:ar_app@localhost:15432/agentic_runtime"
    template = "postgresql+asyncpg://ar_app:ar_app@localhost:{port}/agentic_runtime"
    assert align_local_value(custom, template, 5432, 5432) == (
        "postgresql+asyncpg://ar_app:ar_app@localhost:5432/agentic_runtime"
    )
    remote = "postgresql+asyncpg://ar_app:ar_app@postgres:15432/agentic_runtime"
    assert align_local_value(remote, template, 5432, 5432) == remote
    assert align_local_value("", template, 5432, 5432) == ""


def test_settings_follow_an_explicit_host_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ar_common.host_ports.merged_env", lambda: {})
    monkeypatch.delenv("AR_DATABASE_URL", raising=False)
    monkeypatch.delenv("AR_VALKEY_URL", raising=False)
    settings = BaseServiceSettings(_env_file=None)
    apply_host_ports(settings, {"AR_PG_HOST_PORT": "15432", "AR_PORT": "18000"})
    assert settings.database_url.endswith("@localhost:15432/agentic_runtime")
    assert settings.valkey_url == "redis://localhost:6379/0"


def test_settings_keep_a_database_url_when_the_host_port_is_unset() -> None:
    settings = BaseServiceSettings(_env_file=None)
    settings.database_url = "postgresql+asyncpg://ar_app:ar_app@127.0.0.1:35432/agentic_runtime"
    apply_host_ports(settings, {})
    assert settings.database_url.endswith("@127.0.0.1:35432/agentic_runtime")


def test_listen_port_and_fake_llm_follow_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_PORT", "18000")
    monkeypatch.setenv("AR_FAKE_LLM_HOST_PORT", "18099")
    assert listen_port("AR_PORT", 8000) == 18000
    assert fake_llm_base_url() == "http://127.0.0.1:18099/v1"


def test_health_urls_use_the_defaults_when_unset() -> None:
    urls = health_urls({})
    assert urls[0] == "http://localhost:8000/healthz"
    assert urls[-2] == "http://localhost:8099/healthz"
    assert urls[-1] == "http://localhost:3000/healthz"


def test_published_ports_reads_compose_ps_json() -> None:
    raw = "\n".join(
        (
            '{"Publishers":[{"PublishedPort":5432,"TargetPort":5432}]}',
            '{"Publishers":[{"PublishedPort":0},{"publishedPort":8001}]}',
        )
    )
    assert _published_ports(raw) == {5432, 8001}
    assert _published_ports("not-json") == set()


def test_empty_env_values_use_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_MAX_JSON_BODY_BYTES", "")
    monkeypatch.setenv("AR_TRACE_SAMPLE_RATIO", "")
    settings = BaseServiceSettings(_env_file=None)
    assert settings.max_json_body_bytes == 1_048_576
    assert settings.trace_sample_ratio == 0.1


def test_port_in_use_sees_a_bound_socket() -> None:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
        assert port_in_use(port)
    assert not port_in_use(port)


def test_prepare_reports_a_busy_port_and_the_fix(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AR_DATABASE_URL=postgresql+asyncpg://ar_app:ar_app@localhost:5432/agentic_runtime\n",
        encoding="utf-8",
    )

    def probe(port: int) -> bool:
        return port == 5432

    code, report = prepare_env_file(
        env_file,
        PortCheck(),
        tmp_path / "missing.example",
        probe=probe,
    )
    assert code == 1
    assert "AR_PG_HOST_PORT" in report
    assert "make dev AUTO_PORTS=1" in report


def test_prepare_autofree_rewrites_the_url(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "AR_PG_HOST_PORT=5432",
                "AR_DATABASE_URL=postgresql+asyncpg://ar_app:ar_app@localhost:5432/agentic_runtime",
                "AR_PORT=8000",
                "AR_API_INTERNAL_URL=http://localhost:8000",
                "API_PROXY_URL=http://127.0.0.1:8000",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    def probe(port: int) -> bool:
        return port in {5432, 8000}

    code, report = prepare_env_file(
        env_file,
        PortCheck(auto=True),
        tmp_path / "missing.example",
        probe=probe,
    )
    text = env_file.read_text(encoding="utf-8")
    assert code == 0
    assert "using 5433" in report
    assert "AR_PG_HOST_PORT=5433" in text
    assert "localhost:5433/agentic_runtime" in text
    assert "AR_PORT=8005" in text
    assert "API_PROXY_URL=http://127.0.0.1:8005" in text
    assert "AR_API_INTERNAL_URL=http://localhost:8005" in text
    assert "AR_MG_PORT=" not in text


def test_prepare_moves_model_gateway_and_system_worker(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "AR_MG_PORT=8001",
                "AR_MODEL_GATEWAY_URL=http://localhost:8001",
                "AR_SYSTEM_HOST_PORT=8013",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    def probe(port: int) -> bool:
        return port in {8001, 8013}

    code, report = prepare_env_file(
        env_file,
        PortCheck(auto=True),
        tmp_path / "missing.example",
        probe=probe,
    )
    text = env_file.read_text(encoding="utf-8")
    assert code == 0
    assert "AR_MG_PORT 8001 is in use" in report
    assert "AR_SYSTEM_HOST_PORT 8013 is in use" in report
    assert "AR_MG_PORT=8001\n" not in text
    assert "AR_SYSTEM_HOST_PORT=8013\n" not in text
    assert "AR_MODEL_GATEWAY_URL=http://localhost:8001\n" not in text


def test_prepare_keeps_ports_owned_by_this_compose_project(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AR_PG_HOST_PORT=5432\n"
        "AR_DATABASE_URL=postgresql+asyncpg://ar_app:ar_app@localhost:5432/agentic_runtime\n",
        encoding="utf-8",
    )

    def probe(port: int) -> bool:
        return port == 5432

    code, report = prepare_env_file(
        env_file,
        PortCheck(auto=True),
        tmp_path / "missing.example",
        probe=probe,
        owned={5432},
    )
    text = env_file.read_text(encoding="utf-8")
    assert code == 0
    assert "using " not in report
    assert "AR_PG_HOST_PORT=5432" in text
    assert "localhost:5432/agentic_runtime" in text
