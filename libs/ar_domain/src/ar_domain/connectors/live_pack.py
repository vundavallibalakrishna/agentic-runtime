# ruff: noqa: S106
"""Live-pack canary. Dry unless ``AR_M36_LIVE=1`` and that connector's env is set.

Tokens are read from the environment and never written into the report or the ledger.
A write is not sent unless ``AR_M36_WRITE=1`` and ``AR_M36_WRITE_APPROVED=1``.
GitHub's public read stays the reference call (``octocat/Hello-World`` README).
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

from ar_common.errors import ArError
from ar_common.time import utcnow
from ar_domain.connectors.catalog import CONNECTORS, ConnectorDef, connector_by_slug, tool_by_name

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

# Kinds ``dispatch_connector`` actually runs. A catalogue tool outside this set is a gap.
HANDLED_KINDS = frozenset(
    {
        "http",
        "email_send",
        "email_list",
        "email_read",
        "s3_list",
        "s3_get",
        "s3_put",
        "gdrive_upload",
        "sharepoint_upload",
        "confluence_write",
        "aws",
    }
)

_FLAGS = frozenset(
    {
        "AR_M36_LIVE",
        "AR_M36_WRITE",
        "AR_M36_WRITE_APPROVED",
        "AR_M36_ONLY",
        "AR_M36_LEDGER",
    }
)
_MARKERS = (
    "xoxb-",
    "xoxp-",
    "xoxa-",
    "xoxe-",
    "ghp_",
    "github_pat_",
    "AKIA",
    "ASIA",
    "-----BEGIN",
    "ya29.",
    "pat-",
)
_SAFE = frozenset(
    {"id", "name", "title", "path", "key", "login", "full_name", "number", "displayName"}
)
_LISTS = ("items", "objects", "messages", "records", "value", "channels", "results")
_CANARY = "M36 canary. Safe to delete."


@dataclass(frozen=True, slots=True)
class Canary:
    """One read, and the write that stays held until an operator approves it."""

    slug: str
    read_tool: str
    kind: str
    secret_env: str = ""
    username_env: str = ""
    client_id_env: str = ""
    anonymous: bool = False
    config_env: tuple[tuple[str, str], ...] = ()
    config_default: tuple[tuple[str, str], ...] = ()
    config_optional: tuple[tuple[str, str], ...] = ()
    read_args: tuple[tuple[str, str], ...] = ()
    read_env: tuple[tuple[str, str], ...] = ()
    write_tool: str = ""
    write_args: tuple[tuple[str, str], ...] = ()
    write_env: tuple[tuple[str, str], ...] = ()


def _canary(slug: str, read_tool: str, kind: str, **kwargs: object) -> Canary:
    return Canary(slug=slug, read_tool=read_tool, kind=kind, **kwargs)  # type: ignore[arg-type]


CANARIES: tuple[Canary, ...] = (
    _canary(
        "email",
        "email_list",
        "basic",
        secret_env="AR_M36_EMAIL_PASSWORD",
        username_env="AR_M36_EMAIL_USERNAME",
        config_env=(
            ("smtpHost", "AR_M36_EMAIL_SMTP_HOST"),
            ("imapHost", "AR_M36_EMAIL_IMAP_HOST"),
        ),
        config_default=(
            ("smtpPort", "587"),
            ("imapPort", "993"),
            ("smtpTls", "true"),
            ("imapSsl", "true"),
        ),
        config_optional=(("fromAddress", "AR_M36_EMAIL_FROM"),),
        write_tool="email_send",
        write_args=(("subject", "M36 canary"), ("body", _CANARY)),
        write_env=(("to", "AR_M36_EMAIL_TO"),),
    ),
    _canary(
        "slack",
        "slack_list_channels",
        "bearer",
        secret_env="AR_M36_SLACK_TOKEN",
        write_tool="slack_post_message",
        write_args=(("text", _CANARY),),
        write_env=(("channel", "AR_M36_SLACK_CHANNEL"),),
    ),
    _canary(
        "teams",
        "teams_list_channels",
        "bearer",
        secret_env="AR_M36_TEAMS_TOKEN",
        read_env=(("team", "AR_M36_TEAMS_TEAM"),),
        write_tool="teams_post_message",
        write_args=(("content", _CANARY),),
        write_env=(("team", "AR_M36_TEAMS_TEAM"), ("channel", "AR_M36_TEAMS_CHANNEL")),
    ),
    _canary(
        "gcal",
        "gcal_list_events",
        "bearer",
        secret_env="AR_M36_GCAL_TOKEN",
        write_tool="gcal_create_event",
        write_args=(
            ("summary", "M36 canary"),
            ("start", "2026-12-01T15:00:00Z"),
            ("end", "2026-12-01T15:30:00Z"),
        ),
    ),
    _canary(
        "m365-calendar",
        "m365cal_list_events",
        "bearer",
        secret_env="AR_M36_M365_CALENDAR_TOKEN",
        read_args=(
            ("startDateTime", "2026-11-01T00:00:00Z"),
            ("endDateTime", "2026-11-08T00:00:00Z"),
        ),
        write_tool="m365cal_create_event",
        write_args=(
            ("subject", "M36 canary"),
            ("start", "2026-12-01T15:00:00Z"),
            ("end", "2026-12-01T15:30:00Z"),
        ),
    ),
    _canary(
        "gdrive",
        "gdrive_list",
        "bearer",
        secret_env="AR_M36_GDRIVE_TOKEN",
        write_tool="gdrive_upload",
        write_args=(("name", "m36-canary.txt"), ("text", _CANARY)),
    ),
    _canary(
        "sharepoint",
        "sharepoint_list",
        "bearer",
        secret_env="AR_M36_SHAREPOINT_TOKEN",
        write_tool="sharepoint_upload",
        write_args=(("path", "m36-canary.txt"), ("text", _CANARY)),
    ),
    _canary(
        "s3",
        "s3_list",
        "basic",
        secret_env="AR_M36_S3_SECRET_KEY",
        username_env="AR_M36_S3_ACCESS_KEY",
        config_env=(
            ("endpoint", "AR_M36_S3_ENDPOINT"),
            ("bucket", "AR_M36_S3_BUCKET"),
        ),
        config_default=(("region", "us-east-1"),),
        config_optional=(("region", "AR_M36_S3_REGION"),),
        write_tool="s3_put",
        write_args=(("key", "canary-not-a-secret"), ("text", _CANARY)),
    ),
    _canary(
        "jira",
        "jira_search",
        "basic",
        secret_env="AR_M36_JIRA_TOKEN",
        username_env="AR_M36_JIRA_EMAIL",
        config_env=(("baseUrl", "AR_M36_JIRA_BASE_URL"),),
        read_args=(("jql", "order by created DESC"),),
        write_tool="jira_create_issue",
        write_args=(("summary", "M36 canary"), ("description", _CANARY)),
        write_env=(("project", "AR_M36_JIRA_PROJECT"),),
    ),
    _canary(
        "github",
        "github_read_file",
        "bearer",
        secret_env="AR_M36_GITHUB_TOKEN",
        anonymous=True,
        read_args=(("owner", "octocat"), ("repo", "Hello-World"), ("path", "README")),
        write_tool="github_create_issue",
        write_args=(("title", "M36 canary"), ("body", _CANARY)),
        write_env=(("owner", "AR_M36_GITHUB_OWNER"), ("repo", "AR_M36_GITHUB_REPO")),
    ),
    _canary(
        "confluence",
        "confluence_search",
        "basic",
        secret_env="AR_M36_CONFLUENCE_TOKEN",
        username_env="AR_M36_CONFLUENCE_EMAIL",
        config_env=(("baseUrl", "AR_M36_CONFLUENCE_BASE_URL"),),
        read_args=(("cql", "type=page"),),
        write_tool="confluence_write_page",
        write_args=(("title", "M36 canary"), ("body", _CANARY)),
        write_env=(("space", "AR_M36_CONFLUENCE_SPACE"),),
    ),
    _canary(
        "notion",
        "notion_search",
        "bearer",
        secret_env="AR_M36_NOTION_TOKEN",
        read_args=(("query", ""),),
        write_tool="notion_create_page",
        write_args=(("title", "M36 canary"),),
        write_env=(("parent", "AR_M36_NOTION_PARENT"),),
    ),
    _canary(
        "servicenow",
        "servicenow_query_table",
        "basic",
        secret_env="AR_M36_SERVICENOW_PASSWORD",
        username_env="AR_M36_SERVICENOW_USERNAME",
        config_env=(("baseUrl", "AR_M36_SERVICENOW_BASE_URL"),),
        read_args=(("table", "incident"), ("sysparm_limit", "1")),
        write_tool="servicenow_create_incident",
        write_args=(("short_description", "M36 canary"),),
    ),
    _canary(
        "salesforce",
        "salesforce_query",
        "bearer",
        secret_env="AR_M36_SALESFORCE_TOKEN",
        config_env=(("baseUrl", "AR_M36_SALESFORCE_BASE_URL"),),
        read_args=(("q", "SELECT Id, Name FROM Account LIMIT 1"),),
        write_tool="salesforce_create_record",
        write_env=(("object", "AR_M36_SALESFORCE_OBJECT"), ("fields", "AR_M36_SALESFORCE_FIELDS")),
    ),
    _canary(
        "zendesk",
        "zendesk_search_tickets",
        "basic",
        secret_env="AR_M36_ZENDESK_TOKEN",
        username_env="AR_M36_ZENDESK_EMAIL",
        config_env=(("baseUrl", "AR_M36_ZENDESK_BASE_URL"),),
        read_args=(("query", "type:ticket"),),
        write_tool="zendesk_create_ticket",
        write_args=(("subject", "M36 canary"), ("comment", _CANARY)),
    ),
    _canary(
        "hubspot",
        "hubspot_list_deals",
        "bearer",
        secret_env="AR_M36_HUBSPOT_TOKEN",
        write_tool="hubspot_create_contact",
        write_env=(("email", "AR_M36_HUBSPOT_EMAIL"),),
        write_args=(("firstname", "M36"), ("lastname", "Canary")),
    ),
    _canary(
        "okta",
        "okta_list_users",
        "bearer",
        secret_env="AR_M36_OKTA_TOKEN",
        config_env=(("baseUrl", "AR_M36_OKTA_BASE_URL"),),
        write_tool="okta_deactivate_user",
        write_env=(("user_id", "AR_M36_OKTA_USER_ID"),),
    ),
    _canary(
        "entra",
        "entra_list_users",
        "oauth_client_credentials",
        secret_env="AR_M36_ENTRA_CLIENT_SECRET",
        client_id_env="AR_M36_ENTRA_CLIENT_ID",
        config_env=(("tenantId", "AR_M36_ENTRA_TENANT"),),
    ),
    _canary(
        "aws",
        "aws_list_buckets",
        "basic",
        secret_env="AR_M36_AWS_SECRET_KEY",
        username_env="AR_M36_AWS_ACCESS_KEY",
        config_default=(("region", "us-east-1"),),
        config_optional=(
            ("region", "AR_M36_AWS_REGION"),
            ("roleArn", "AR_M36_AWS_ROLE_ARN"),
            ("endpoint", "AR_M36_AWS_ENDPOINT"),
        ),
    ),
    _canary(
        "azure",
        "azure_list_resource_groups",
        "oauth_client_credentials",
        secret_env="AR_M36_AZURE_CLIENT_SECRET",
        client_id_env="AR_M36_AZURE_CLIENT_ID",
        config_env=(
            ("tenantId", "AR_M36_AZURE_TENANT"),
            ("subscriptionId", "AR_M36_AZURE_SUBSCRIPTION"),
        ),
    ),
    _canary(
        "gcp",
        "gcp_list_projects",
        "api_key",
        secret_env="AR_M36_GCP_SERVICE_ACCOUNT_JSON",
        config_optional=(
            ("projectId", "AR_M36_GCP_PROJECT"),
            ("zone", "AR_M36_GCP_ZONE"),
        ),
    ),
)


def ledger_path() -> Path:
    """Ledger of redacted promotions. ``AR_M36_LEDGER`` overrides the repo file."""
    override = os.environ.get("AR_M36_LEDGER", "").strip()
    if override:
        return Path(override)
    return _repo_root() / "docs" / "testing" / "m36" / "ledger.json"


def shown_verification(connector: ConnectorDef) -> str:
    """Catalog label, promoted to live when the ledger recorded a read."""
    if connector.verification in {"live", "public"}:
        return connector.verification
    if promotions().get(connector.slug) == "live":
        return "live"
    return connector.verification


def promotions() -> dict[str, str]:
    """Slug to ``live`` for ledger rows a canary recorded. Missing file is empty."""
    path = ledger_path()
    if not path.is_file():
        return {}
    try:
        payload = orjson.loads(path.read_bytes())
    except orjson.JSONDecodeError:
        return {}
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    found: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "")
        if row.get("verification") != "live" or connector_by_slug(slug) is None:
            continue
        blob = orjson.dumps(row).decode()
        if not evidence_allowed(blob):
            continue
        found[slug] = "live"
    return found


def evidence_allowed(text: str) -> bool:
    """False when text still carries a token prefix."""
    return not any(marker in text for marker in _MARKERS)


def run_pack(
    environ: Mapping[str, str] | None = None,
    *,
    transport: object | None = None,
) -> list[dict[str, object]]:
    """Run every canary. An empty mapping is a dry run and does not open the network."""
    env = os.environ if environ is None else environ
    live = env.get("AR_M36_LIVE", "") == "1"
    only = {item.strip() for item in env.get("AR_M36_ONLY", "").split(",") if item.strip()}
    secrets = _secret_values(env)
    selected = [item for item in CANARIES if not only or item.slug in only]
    rows: list[dict[str, object]] = []
    session: tuple[object, object] | None = None
    for canary in selected:
        if not live:
            rows.append(_skipped(canary, "dry"))
            continue
        missing = _read_missing(canary, env)
        if missing:
            rows.append(_skipped(canary, "missing_env", missing=missing))
            continue
        if session is None:
            session = _session(transport)
        rows.append(_call(canary, env, session[0], session[1], secrets))
    return rows


def render_report(rows: list[dict[str, object]]) -> str:
    """Plain text. Env values are not included."""
    lines = [
        "slug implementation catalog verification outcome reason read write missing",
    ]
    for row in rows:
        missing = row.get("missing")
        names = ",".join(missing) if isinstance(missing, list) else ""
        read = row.get("read")
        write = row.get("write")
        read_tool = read.get("tool") if isinstance(read, dict) else ""
        write_status = write.get("status") if isinstance(write, dict) else ""
        lines.append(
            " ".join(
                [
                    str(row.get("slug") or ""),
                    str(row.get("implementation") or ""),
                    str(row.get("catalog") or ""),
                    str(row.get("verification") or ""),
                    str(row.get("outcome") or ""),
                    str(row.get("reason") or "-"),
                    f"read={read_tool}",
                    f"write={write_status}",
                    names,
                ]
            )
        )
    return "\n".join(lines) + "\n"


def record_promotions(
    rows: list[dict[str, object]],
    path: Path,
    *,
    secrets: tuple[str, ...] = (),
) -> list[str]:
    """Store redacted live rows. Returns slugs that were refused."""
    current = _load_rows(path)
    by_slug = {str(item.get("slug")): item for item in current if isinstance(item, dict)}
    refused: list[str] = []
    for row in rows:
        if row.get("outcome") != "live":
            continue
        slug = str(row.get("slug") or "")
        read = _as_dict(row.get("read"))
        write = _as_dict(row.get("write"))
        stored = {
            "slug": slug,
            "verification": "live",
            "tool": str(read.get("tool") or ""),
            "target": _scrub(str(read.get("target") or ""), secrets),
            "excerpt": _scrub(str(read.get("excerpt") or "ok"), secrets),
            "write": str(write.get("status") or ""),
            "at": utcnow().isoformat(),
        }
        if not evidence_allowed(orjson.dumps(stored).decode()):
            refused.append(slug)
            continue
        by_slug[slug] = stored
    payload = {
        "version": 1,
        "note": "Redacted canary ledger. No tokens.",
        "rows": list(by_slug.values()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2) + b"\n")
    return refused


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    """Print the report. ``--record`` updates the ledger. Exit 1 when a live call fails."""
    args = list(sys.argv[1:] if argv is None else argv)
    env = os.environ if environ is None else environ
    rows = run_pack(env)
    sys.stdout.write(render_report(rows))
    if "--record" in args:
        refused = record_promotions(rows, ledger_path(), secrets=_secret_values(env))
        if refused:
            sys.stdout.write("refused " + ",".join(refused) + "\n")
        else:
            sys.stdout.write("recorded ledger\n")
    if any(row.get("outcome") == "failed" for row in rows):
        return 1
    return 0


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "docs").is_dir():
            return parent
    return here.parents[5]


def _secret_values(env: Mapping[str, str]) -> tuple[str, ...]:
    values = [
        value
        for key, value in env.items()
        if key.startswith("AR_M36_") and key not in _FLAGS and len(value) >= 8
    ]
    values.sort(key=len, reverse=True)
    return tuple(values)


def _scrub(text: str, secrets: tuple[str, ...]) -> str:
    cleaned = text
    for secret in secrets:
        if secret and secret in cleaned:
            cleaned = cleaned.replace(secret, "[redacted]")
    return cleaned


def _session(transport: object | None) -> tuple[Any, Any]:
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.chat.service import ChatService  # noqa: PLC0415
    from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415

    store = ChatService()
    if transport is not None:
        store.connector_transport = transport  # type: ignore[attr-defined]
    actor = Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)
    return store, actor


def _skipped(canary: Canary, reason: str, *, missing: list[str] | None = None) -> dict[str, object]:
    connector = connector_by_slug(canary.slug)
    catalog = connector.verification if connector is not None else "not_live"
    return {
        "slug": canary.slug,
        "implementation": "built",
        "catalog": catalog,
        "verification": catalog,
        "outcome": "skipped",
        "reason": reason,
        "missing": list(missing or []),
        "read": _empty_read(canary),
        "write": {"status": "dry" if reason == "dry" else "skipped", "tool": canary.write_tool},
    }


def _call(
    canary: Canary,
    env: Mapping[str, str],
    store: Any,
    actor: Any,
    secrets: tuple[str, ...],
) -> dict[str, object]:
    connector = connector_by_slug(canary.slug)
    catalog = connector.verification if connector is not None else "not_live"
    base: dict[str, object] = {
        "slug": canary.slug,
        "implementation": "built",
        "catalog": catalog,
        "missing": [],
        "read": _empty_read(canary),
        "write": {"status": "none", "tool": canary.write_tool},
    }
    try:
        _install(store, actor, canary, env)
    except ArError as exc:
        base.update(outcome="failed", reason="install", verification=catalog)
        read = _as_dict(base["read"])
        read["code"] = exc.__class__.__name__
        read["excerpt"] = _scrub(exc.__class__.__name__, secrets)
        base["read"] = read
        return base
    arguments = _merged(canary.read_args, canary.read_env, env)
    result = _dispatch(store, actor, canary.read_tool, arguments)
    read_ok = result.get("is_error") is False
    excerpt = _excerpt(result.get("structured"), secrets) if read_ok else ""
    base["read"] = {
        "ok": read_ok,
        "tool": canary.read_tool,
        "target": _target(canary.read_args),
        "excerpt": excerpt or ("ok" if read_ok else ""),
        "code": "" if read_ok else str(result.get("code") or "upstream_error"),
    }
    write_status, write_args = _write_plan(canary, env)
    if write_status == "call":
        written = _dispatch(store, actor, canary.write_tool, write_args)
        write_status = "ok" if written.get("is_error") is False else "failed"
    base["write"] = {"status": write_status, "tool": canary.write_tool}
    if not read_ok or write_status == "failed":
        base.update(outcome="failed", reason="call", verification=catalog)
        return base
    promoted = "live" if catalog == "not_live" else catalog
    base.update(outcome="live", reason="read", verification=promoted)
    return base


def _install(store: Any, actor: Any, canary: Canary, env: Mapping[str, str]) -> None:
    from ar_domain.connectors.book import ConnectorBook  # noqa: PLC0415

    secret = env.get(canary.secret_env, "") if canary.secret_env else ""
    if canary.anonymous and not secret:
        ConnectorBook(store).install(actor, canary.slug, {"connection_name": "public"})
        return
    config = dict(canary.config_default)
    for key, name in canary.config_env:
        config[key] = env.get(name, "")
    for key, name in canary.config_optional:
        if env.get(name):
            config[key] = env[name]
    if canary.slug == "email" and not config.get("fromAddress"):
        config["fromAddress"] = env.get(canary.username_env, "")
    ConnectorBook(store).install(
        actor,
        canary.slug,
        {
            "connection_name": ("m36" + canary.slug.replace("-", ""))[:40],
            "kind": canary.kind,
            "secret": secret,
            "username": env.get(canary.username_env, "") if canary.username_env else "",
            "client_id": env.get(canary.client_id_env, "") if canary.client_id_env else "",
            "config": config,
        },
    )


def _dispatch(store: Any, actor: Any, tool: str, arguments: dict[str, object]) -> dict[str, object]:
    from ar_domain.connectors.dispatch import dispatch_connector  # noqa: PLC0415

    tenant = getattr(actor, "tenant_id", "")
    user = getattr(actor, "user_id", "")
    result = dispatch_connector(store, tool, {**arguments, "_tenant_id": tenant, "_user_id": user})
    return result if isinstance(result, dict) else {"is_error": True, "code": "upstream_error"}


def _write_plan(canary: Canary, env: Mapping[str, str]) -> tuple[str, dict[str, object]]:
    if not canary.write_tool:
        return "none", {}
    if env.get("AR_M36_WRITE", "") != "1":
        return "held", {}
    if env.get("AR_M36_WRITE_APPROVED", "") != "1":
        return "awaiting_approval", {}
    missing = _write_missing(canary, env)
    if missing:
        return "missing_env", {}
    return "call", _merged(canary.write_args, canary.write_env, env)


def _read_missing(canary: Canary, env: Mapping[str, str]) -> list[str]:
    missing: list[str] = []
    if canary.secret_env and not canary.anonymous and not env.get(canary.secret_env):
        missing.append(canary.secret_env)
    if canary.username_env and not env.get(canary.username_env):
        missing.append(canary.username_env)
    if canary.client_id_env and not env.get(canary.client_id_env):
        missing.append(canary.client_id_env)
    for _key, name in (*canary.config_env, *canary.read_env):
        if not env.get(name):
            missing.append(name)
    return missing


def _write_missing(canary: Canary, env: Mapping[str, str]) -> list[str]:
    missing = [name for _key, name in canary.write_env if not env.get(name)]
    if canary.secret_env and not env.get(canary.secret_env):
        missing.append(canary.secret_env)
    return missing


def _merged(
    literals: tuple[tuple[str, str], ...],
    sourced: tuple[tuple[str, str], ...],
    env: Mapping[str, str],
) -> dict[str, object]:
    arguments: dict[str, object] = dict(literals)
    for key, name in sourced:
        if env.get(name):
            arguments[key] = env[name]
    return arguments


def _as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _empty_read(canary: Canary) -> dict[str, object]:
    return {
        "ok": False,
        "tool": canary.read_tool,
        "target": _target(canary.read_args),
        "excerpt": "",
        "code": "",
    }


def _target(literals: tuple[tuple[str, str], ...]) -> str:
    return "/".join(value for _key, value in literals if value)[:120]


def _excerpt(structured: object, secrets: tuple[str, ...]) -> str:
    parts: list[str] = []
    if isinstance(structured, dict):
        for key in _LISTS:
            found = structured.get(key)
            if isinstance(found, list):
                parts.append(f"{key}={len(found)}")
                if found and isinstance(found[0], dict):
                    parts.append(_fields(found[0]))
                break
        else:
            parts.append(_fields(structured))
    text = " ".join(part for part in parts if part)[:180]
    return _scrub(text, secrets)


def _fields(row: dict[str, object]) -> str:
    bits = []
    for key in _SAFE:
        value = row.get(key)
        if value in {None, ""}:
            continue
        bits.append(f"{key}={value}")
    return " ".join(bits)[:120]


def _load_rows(path: Path) -> list[object]:
    if not path.is_file():
        return []
    try:
        payload = orjson.loads(path.read_bytes())
    except orjson.JSONDecodeError:
        return []
    rows = payload.get("rows") if isinstance(payload, dict) else None
    return list(rows) if isinstance(rows, list) else []


def catalogue_gap() -> list[str]:
    """Tools whose kind dispatch does not run, or canaries that name a missing tool."""
    problems: list[str] = []
    slugs = {item.slug for item in CANARIES}
    for connector in CONNECTORS:
        if connector.slug not in slugs:
            problems.append(f"missing canary {connector.slug}")
        if connector.implementation != "built":
            problems.append(f"{connector.slug} is not built")
        problems.extend(
            f"{tool.name} kind {tool.kind}"
            for tool in connector.tools
            if tool.kind not in HANDLED_KINDS
        )
    for canary in CANARIES:
        if tool_by_name(canary.read_tool) is None:
            problems.append(f"unknown read {canary.read_tool}")
        if canary.write_tool and tool_by_name(canary.write_tool) is None:
            problems.append(f"unknown write {canary.write_tool}")
        found = tool_by_name(canary.read_tool)
        if found is not None and found[1].risk != "R0":
            problems.append(f"{canary.read_tool} is not a read")
        written = tool_by_name(canary.write_tool) if canary.write_tool else None
        if written is not None and written[1].risk != "W2":
            problems.append(f"{canary.write_tool} is not a write")
        owner = connector_by_slug(canary.slug)
        writes = [tool.name for tool in owner.tools if tool.risk == "W2"] if owner else []
        if writes and canary.write_tool not in writes:
            problems.append(f"{canary.slug} write is not a catalogue write")
        if not writes and canary.write_tool:
            problems.append(f"{canary.slug} has no write")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
