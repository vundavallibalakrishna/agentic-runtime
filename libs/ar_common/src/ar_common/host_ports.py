"""Local host ports and the localhost URLs that follow them.

Compose publishes ``${AR_PG_HOST_PORT:-5432}``. ``make dev`` and settings copy
that same port into ``AR_DATABASE_URL`` when the host is localhost. Container
ports for databases stay fixed; app processes listen on the published port.
"""

import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})


@dataclass(frozen=True)
class HostPort:
    """One TCP port published on the developer machine."""

    name: str
    default: int
    service: str
    profiles: frozenset[str]


@dataclass(frozen=True)
class UrlBinding:
    """An env value whose localhost port tracks a host port."""

    env_key: str
    port_name: str
    template: str
    attr: str = ""


@dataclass(frozen=True)
class PortCheck:
    """Which compose profiles and whether busy ports may move."""

    auto: bool = False
    dev_min: bool = False
    obs: bool = False
    scan: bool = False
    qdrant: bool = False


HOST_PORTS: tuple[HostPort, ...] = (
    HostPort("AR_PG_HOST_PORT", 5432, "postgres", frozenset({"deps"})),
    HostPort("AR_VALKEY_HOST_PORT", 6379, "valkey", frozenset({"deps"})),
    HostPort("AR_TEMPORAL_HOST_PORT", 7233, "temporal", frozenset({"deps"})),
    HostPort("AR_TEMPORAL_UI_HOST_PORT", 8233, "temporal-ui", frozenset({"deps"})),
    HostPort("AR_KEYCLOAK_HOST_PORT", 8180, "keycloak", frozenset({"deps"})),
    HostPort("AR_S3_HOST_PORT", 8333, "seaweedfs", frozenset({"deps"})),
    HostPort("AR_VAULT_HOST_PORT", 8200, "openbao", frozenset({"deps"})),
    HostPort("AR_OPA_HOST_PORT", 8181, "opa", frozenset({"deps"})),
    HostPort("AR_SMTP_PORT", 1025, "mailpit-smtp", frozenset({"deps"})),
    HostPort("AR_MAILPIT_UI_HOST_PORT", 8025, "mailpit-ui", frozenset({"deps"})),
    HostPort("AR_EGRESS_HOST_PORT", 3128, "squid", frozenset({"deps"})),
    HostPort("AR_CLAMAV_HOST_PORT", 3310, "clamav", frozenset({"scan"})),
    HostPort("AR_QDRANT_HTTP_HOST_PORT", 6333, "qdrant-http", frozenset({"qdrant"})),
    HostPort("AR_QDRANT_GRPC_HOST_PORT", 6334, "qdrant-grpc", frozenset({"qdrant"})),
    HostPort("AR_OTEL_GRPC_HOST_PORT", 4317, "otel-grpc", frozenset({"obs"})),
    HostPort("AR_OTEL_HTTP_HOST_PORT", 4318, "otel-http", frozenset({"obs"})),
    HostPort("AR_PROMETHEUS_HOST_PORT", 9090, "prometheus", frozenset({"obs"})),
    HostPort("AR_TEMPO_HOST_PORT", 3200, "tempo", frozenset({"obs"})),
    HostPort("AR_GRAFANA_HOST_PORT", 3001, "grafana", frozenset({"obs"})),
    HostPort("AR_LANGFUSE_HOST_PORT", 3100, "langfuse", frozenset({"obs"})),
    HostPort("AR_CLICKHOUSE_HOST_PORT", 8123, "clickhouse", frozenset({"obs"})),
    HostPort("AR_PORT", 8000, "api", frozenset({"dev", "dev-min"})),
    HostPort("AR_MG_PORT", 8001, "model-gateway", frozenset({"dev", "dev-min"})),
    HostPort("AR_MCPG_PORT", 8002, "mcp-gateway", frozenset({"dev", "dev-min"})),
    HostPort("AR_SANDBOX_MANAGER_HOST_PORT", 8003, "sandbox-manager", frozenset({"dev"})),
    HostPort("AR_CHANNELS_PORT", 8004, "channels", frozenset({"dev"})),
    HostPort("AR_MCP_SQL_HOST_PORT", 8010, "mcp-sql", frozenset({"dev"})),
    HostPort("AR_MCP_OPENAPI_HOST_PORT", 8011, "mcp-openapi", frozenset({"dev"})),
    HostPort("AR_RUNTIME_HOST_PORT", 8012, "runtime-worker", frozenset({"dev", "dev-min"})),
    HostPort("AR_SYSTEM_HOST_PORT", 8013, "system-worker", frozenset({"dev", "dev-min"})),
    HostPort("AR_INGEST_HOST_PORT", 8014, "ingest-worker", frozenset({"dev"})),
    HostPort("AR_SANDBOX_AGENT_HOST_PORT", 8080, "sandbox-agent", frozenset({"dev"})),
    HostPort("AR_FAKE_LLM_HOST_PORT", 8099, "fake-llm", frozenset({"dev", "dev-min"})),
    HostPort("AR_WEB_HOST_PORT", 3000, "web", frozenset({"dev", "dev-min"})),
)

URL_BINDINGS: tuple[UrlBinding, ...] = (
    UrlBinding(
        "AR_DATABASE_URL",
        "AR_PG_HOST_PORT",
        "postgresql+asyncpg://ar_app:ar_app@localhost:{port}/agentic_runtime",
        "database_url",
    ),
    UrlBinding(
        "AR_VALKEY_URL",
        "AR_VALKEY_HOST_PORT",
        "redis://localhost:{port}/0",
        "valkey_url",
    ),
    UrlBinding("AR_S3_ENDPOINT", "AR_S3_HOST_PORT", "http://localhost:{port}", "s3_endpoint"),
    UrlBinding(
        "AR_S3_PUBLIC_ENDPOINT",
        "AR_S3_HOST_PORT",
        "http://localhost:{port}",
        "s3_public_endpoint",
    ),
    UrlBinding(
        "AR_OTEL_EXPORTER_OTLP_ENDPOINT",
        "AR_OTEL_GRPC_HOST_PORT",
        "http://localhost:{port}",
        "otel_exporter_otlp_endpoint",
    ),
    UrlBinding("AR_PUBLIC_URL", "AR_WEB_HOST_PORT", "http://localhost:{port}", "public_url"),
    UrlBinding(
        "AR_OIDC_ISSUER",
        "AR_KEYCLOAK_HOST_PORT",
        "http://localhost:{port}/realms/agentic-runtime",
        "oidc_issuer",
    ),
    UrlBinding("AR_VAULT_ADDR", "AR_VAULT_HOST_PORT", "http://localhost:{port}", "vault_addr"),
    UrlBinding("AR_TEMPORAL_ADDRESS", "AR_TEMPORAL_HOST_PORT", "localhost:{port}"),
    UrlBinding("AR_OPA_URL", "AR_OPA_HOST_PORT", "http://localhost:{port}"),
    UrlBinding("AR_EGRESS_PROXY_URL", "AR_EGRESS_HOST_PORT", "http://localhost:{port}"),
    UrlBinding("AR_CLAMAV_ADDRESS", "AR_CLAMAV_HOST_PORT", "localhost:{port}"),
    UrlBinding("AR_QDRANT_URL", "AR_QDRANT_HTTP_HOST_PORT", "http://localhost:{port}"),
    UrlBinding("AR_TRACE_UI_URL", "AR_GRAFANA_HOST_PORT", "http://localhost:{port}"),
    UrlBinding("AR_MODEL_GATEWAY_URL", "AR_MG_PORT", "http://localhost:{port}"),
    UrlBinding("AR_MCP_GATEWAY_URL", "AR_MCPG_PORT", "http://localhost:{port}"),
    UrlBinding("AR_API_INTERNAL_URL", "AR_PORT", "http://localhost:{port}"),
    UrlBinding("API_PROXY_URL", "AR_PORT", "http://127.0.0.1:{port}"),
)

PORT_BY_NAME: dict[str, HostPort] = {spec.name: spec for spec in HOST_PORTS}

_HEALTH: tuple[str, ...] = (
    "AR_PORT",
    "AR_MG_PORT",
    "AR_MCPG_PORT",
    "AR_SANDBOX_MANAGER_HOST_PORT",
    "AR_CHANNELS_PORT",
    "AR_MCP_SQL_HOST_PORT",
    "AR_MCP_OPENAPI_HOST_PORT",
    "AR_RUNTIME_HOST_PORT",
    "AR_SYSTEM_HOST_PORT",
    "AR_INGEST_HOST_PORT",
    "AR_SANDBOX_AGENT_HOST_PORT",
    "AR_FAKE_LLM_HOST_PORT",
    "AR_WEB_HOST_PORT",
)


def find_env_file() -> Path | None:
    """Return the repo ``.env``, searching parents for ``compose.yaml``."""
    current = Path.cwd()
    for directory in (current, *current.parents):
        if (directory / "compose.yaml").is_file() and (directory / ".env").is_file():
            return directory / ".env"
        if directory == directory.parent:
            break
    direct = current / ".env"
    return direct if direct.is_file() else None


def parse_env(path: Path) -> dict[str, str]:
    """Read ``KEY=VALUE`` lines. Blank and comment lines are ignored."""
    found: dict[str, str] = {}
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        found[key.strip()] = value.strip().strip('"').strip("'")
    return found


def merged_env() -> dict[str, str]:
    """``.env`` values with the process environment winning."""
    found = parse_env(find_env_file() or Path(".env"))
    for key, value in os.environ.items():
        if value.strip():
            found[key] = value.strip()
    return found


def resolved_port(spec: HostPort, env: Mapping[str, str]) -> int:
    """Return the configured host port, or the default when unset."""
    raw = env.get(spec.name, "").strip()
    if not raw:
        return spec.default
    if not raw.isdigit():
        message = f"{spec.name} must be an integer, got {raw}"
        raise ValueError(message)
    port = int(raw)
    if port < 1 or port > 65535:
        message = f"{spec.name} must be between 1 and 65535"
        raise ValueError(message)
    return port


def rewrite_local_port(value: str, port: int) -> str:
    """Replace the port when the host is localhost or 127.0.0.1."""
    if "://" in value:
        parts = urlsplit(value)
        host = parts.hostname
        if host not in _LOCAL_HOSTS:
            return value
        user = ""
        if parts.username is not None:
            user = parts.username
            if parts.password is not None:
                user += f":{parts.password}"
            user += "@"
        netloc = f"{user}{host}:{port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    host, sep, old = value.rpartition(":")
    if sep and host in _LOCAL_HOSTS and old.isdigit():
        return f"{host}:{port}"
    return value


def align_local_value(current: str, template: str, port: int, default: int) -> str:
    """Keep ``current`` unless ``port`` moved off the default."""
    if port == default:
        return current
    if current.strip() == "":
        return template.format(port=port)
    return rewrite_local_port(current, port)


def apply_host_ports(target: object, env: Mapping[str, str] | None = None) -> None:
    """Rewrite localhost settings fields from the host-port variables."""
    source = merged_env() if env is None else env
    for binding in URL_BINDINGS:
        if not binding.attr or not hasattr(target, binding.attr):
            continue
        current = getattr(target, binding.attr)
        if not isinstance(current, str):
            continue
        spec = PORT_BY_NAME[binding.port_name]
        port = resolved_port(spec, source)
        updated = align_local_value(current, binding.template, port, spec.default)
        setattr(target, binding.attr, updated)


def listen_port(name: str, default: int) -> int:
    """Port a honcho process should bind."""
    spec = PORT_BY_NAME.get(name)
    if spec is None:
        raw = merged_env().get(name, "").strip()
        return int(raw) if raw.isdigit() else default
    return resolved_port(spec, merged_env())


def local_endpoint(env_key: str, template: str, port_name: str) -> str:
    """Resolve one localhost endpoint from the env and its host port."""
    spec = PORT_BY_NAME[port_name]
    env = merged_env()
    port = resolved_port(spec, env)
    current = env.get(env_key, "").strip() or template.format(port=spec.default)
    return align_local_value(current, template, port, spec.default)


def fake_llm_port() -> int:
    """Listen port for fake-llm. ``FAKE_LLM_PORT`` still works."""
    env = merged_env()
    legacy = env.get("FAKE_LLM_PORT", "").strip()
    if not env.get("AR_FAKE_LLM_HOST_PORT", "").strip() and legacy:
        env = {**env, "AR_FAKE_LLM_HOST_PORT": legacy}
    spec = PORT_BY_NAME["AR_FAKE_LLM_HOST_PORT"]
    return resolved_port(spec, env)


def fake_llm_base_url() -> str:
    """OpenAI-compatible base URL for the local fake-llm process."""
    spec = PORT_BY_NAME["AR_FAKE_LLM_HOST_PORT"]
    return align_local_value(
        "http://127.0.0.1:8099/v1",
        "http://127.0.0.1:{port}/v1",
        fake_llm_port(),
        spec.default,
    )


def health_urls(env: Mapping[str, str] | None = None) -> list[str]:
    """Compose-smoke health URLs on the configured host ports."""
    source = merged_env() if env is None else env
    return [
        f"http://localhost:{resolved_port(PORT_BY_NAME[name], source)}/healthz" for name in _HEALTH
    ]


def port_in_use(port: int) -> bool:
    """True when this machine cannot bind the port."""
    for address in ("127.0.0.1", "0.0.0.0"):  # noqa: S104
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((address, port))
            except OSError:
                return True
    return False


def active_ports(check: PortCheck) -> tuple[HostPort, ...]:
    """Ports ``make dev`` will publish for the selected profiles."""
    profiles = {"deps", "dev-min" if check.dev_min else "dev"}
    if check.obs:
        profiles.add("obs")
    if check.scan:
        profiles.add("scan")
    if check.qdrant:
        profiles.add("qdrant")
    return tuple(spec for spec in HOST_PORTS if spec.profiles & profiles)


def _next_free(start: int, chosen: set[int], probe: Callable[[int], bool]) -> int:
    candidate = start + 1
    while candidate <= 65535:
        if candidate not in chosen and not probe(candidate):
            return candidate
        candidate += 1
    message = "no free TCP port"
    raise ValueError(message)


def assign_ports(
    specs: Sequence[HostPort],
    env: dict[str, str],
    *,
    auto: bool,
    probe: Callable[[int], bool],
) -> list[str]:
    """Record busy ports, or move them when ``auto`` is set."""
    notes: list[str] = []
    desired = {spec.name: resolved_port(spec, env) for spec in specs}
    blocked = set(desired.values())
    chosen: set[int] = set()
    for spec in specs:
        current = desired[spec.name]
        if current not in chosen and not probe(current):
            chosen.add(current)
            continue
        if not auto:
            notes.append(f"  {current:<5}  {spec.name}  ({spec.service})")
            chosen.add(current)
            continue
        replacement = _next_free(current, blocked | chosen, probe)
        env[spec.name] = str(replacement)
        blocked.add(replacement)
        chosen.add(replacement)
        notes.append(f"{spec.name} {current} is in use; using {replacement}")
    return notes


def derived_updates(env: Mapping[str, str]) -> dict[str, str]:
    """Env assignments that make localhost URLs follow the host ports."""
    updates: dict[str, str] = {}
    for binding in URL_BINDINGS:
        spec = PORT_BY_NAME[binding.port_name]
        port = resolved_port(spec, env)
        current = env.get(binding.env_key, "")
        updated = align_local_value(current, binding.template, port, spec.default)
        if updated not in (current, ""):
            updates[binding.env_key] = updated
    return updates


def update_env_file(path: Path, updates: Mapping[str, str]) -> None:
    """Replace or append ``KEY=VALUE`` lines, preserving comments."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    seen: set[str] = set()
    rewritten: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            rewritten.append(line)
            continue
        key, _, _value = stripped.partition("=")
        name = key.strip()
        if name in updates:
            rewritten.append(f"{name}={updates[name]}")
            seen.add(name)
        else:
            rewritten.append(line)
    for key, value in updates.items():
        if key not in seen:
            rewritten.append(f"{key}={value}")
    path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def _port_updates(
    specs: Sequence[HostPort],
    original: Mapping[str, str],
    env: Mapping[str, str],
) -> dict[str, str]:
    updates: dict[str, str] = {}
    for spec in specs:
        new = env.get(spec.name, "").strip()
        old = original.get(spec.name, "").strip()
        if not new or new == old:
            continue
        if new == str(spec.default) and not old:
            continue
        updates[spec.name] = new
    return updates


def prepare_env_file(
    env_file: Path,
    check: PortCheck,
    example: Path,
    *,
    probe: Callable[[int], bool] | None = None,
) -> tuple[int, str]:
    """Sync localhost URLs, then report or move busy ports. Returns an exit code."""
    original = parse_env(env_file)
    env = dict(original)
    for spec in HOST_PORTS:
        exported = os.environ.get(spec.name, "").strip()
        if exported:
            env[spec.name] = exported
    specs = active_ports(check)
    in_use = port_in_use if probe is None else probe
    notes = assign_ports(specs, env, auto=check.auto, probe=in_use)
    merged = {**original, **{key: value for key, value in env.items() if value.strip()}}
    updates = _port_updates(specs, original, env)
    updates.update(derived_updates(merged))
    if updates:
        if not env_file.is_file() and example.is_file():
            env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        update_env_file(env_file, updates)
    return _report(auto=check.auto, notes=notes, wrote=bool(updates))


def _report(*, auto: bool, notes: list[str], wrote: bool) -> tuple[int, str]:
    if notes and not auto:
        lines = [
            "Host ports already in use:",
            *notes,
            "",
            "Edit those variables in .env. Each one sets the published port and the",
            "localhost URL that uses it (AR_PG_HOST_PORT updates AR_DATABASE_URL,",
            "AR_PORT updates the API and API_PROXY_URL).",
            "Or pick free ports: make dev AUTO_PORTS=1",
        ]
        return 1, "\n".join(lines)
    lines = list(notes)
    if wrote:
        lines.append("Updated .env so localhost URLs match the host ports.")
    lines.append("Host ports are free.")
    return 0, "\n".join(lines)
