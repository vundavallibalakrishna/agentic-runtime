"""ADR-0032 proof labels and the capability matrix.

Only ``unit``, ``contract``, and ``live`` are proof labels. A mock transport is
``unit``. A connector with a recorded HTTP fixture is ``contract`` and is not
offered. ``public`` is ``contract`` (real HTTP, no customer account). ``live``
is a customer or provider account and is the only label that is offered.

Built-in tools run in this process. They stay offered and are labelled ``unit``.
They are not a recorded live model run. See OQ-123.
"""

from __future__ import annotations

from pathlib import Path

UNIT = "unit"
CONTRACT = "contract"
LIVE = "live"
LABELS = frozenset({UNIT, CONTRACT, LIVE})

# Stage 2 moves these out of core. The matrix does not list them as core features.
_OMITTED_PREFIXES = ("records.",)
_OMITTED_NAMES = frozenset({"documents.fill_questionnaire"})

_CAPABILITIES: tuple[tuple[str, str, str, str], ...] = (
    (
        "chat",
        UNIT,
        "no",
        "The API reads and writes Postgres per request. The worker runs one step "
        "per activity and calls the tool gateway over HTTP. No stored report "
        "names a model id and a date.",
    ),
    ("agents", UNIT, "no", "Definitions and publish run in process."),
    (
        "builder",
        UNIT,
        "no",
        "A draft uses the tenant model when one is set. No stored live report.",
    ),
    (
        "password-sign-in",
        CONTRACT,
        "no",
        "Password login is the dev and single-tenant door. It is not the Helm default.",
    ),
    ("approvals", UNIT, "no", "Four-eyes decisions run in process."),
    ("audit", UNIT, "no", "The hash chain is written in process."),
    ("files", UNIT, "no", "File tools run in process."),
    (
        "knowledge",
        UNIT,
        "no",
        "Retrieval runs in process. No stored live embedding report.",
    ),
    (
        "memory",
        CONTRACT,
        "no",
        "Conversation summaries are rows in Postgres and a second replica reads them. "
        "No stored report names a model id and a date.",
    ),
    ("skills", UNIT, "no", "Loading a skill runs in process."),
    (
        "documents",
        UNIT,
        "no",
        "Read and summarise run in process. A cloud OCR engine is not live.",
    ),
    (
        "oidc-sign-in",
        CONTRACT,
        "no",
        "Authorization code and JWKS bearer. Contract proof uses a local mock IdP.",
    ),
    (
        "evals",
        UNIT,
        "no",
        "The dry-run gym is unit. Lexical overlap is not_judged and is not a verdict.",
    ),
    (
        "planning",
        UNIT,
        "no",
        "An optional plan step runs in process. No stored report names a model id and a date.",
    ),
    (
        "repair",
        UNIT,
        "no",
        "Schema and parse retries run in process. The tool-failure notice is a structured field.",
    ),
    (
        "model-routing",
        UNIT,
        "no",
        "Fallback and the circuit breaker run in process. Valkey holds circuit state outside dev.",
    ),
    (
        "context",
        CONTRACT,
        "no",
        "A worker activity folds older messages into the Postgres summary. "
        "The fold does not call a model.",
    ),
    (
        "eval-harness",
        CONTRACT,
        "no",
        "An eval is an eval run in the product.",
    ),
    (
        "research",
        UNIT,
        "no",
        "Research searches the tenant's document library and, when one is configured, the "
        "web provider general.search uses. Unit tests add library notes. No stored live report.",
    ),
)


# Recorded HTTP fixtures (public API examples, tokens scrubbed). Still not offered.
RECORDED_FIXTURES = frozenset(
    {
        "slack",
        "gdrive",
        "gcal",
        "gmail",
        "outlook",
        "sharepoint",
        "teams",
        "jira",
        "confluence",
        "rest",
    }
)


def proof_from_verification(verification: str) -> str:
    """Map a catalogue verification word onto an ADR-0032 label."""
    if verification == "live":
        return LIVE
    if verification == "public":
        return CONTRACT
    return UNIT


def connector_proof(connector: object) -> str:
    """The proof a person should see for this connector, after any recorded read."""
    from ar_domain.connectors.catalog import ConnectorDef  # noqa: PLC0415
    from ar_domain.connectors.live_pack import shown_verification  # noqa: PLC0415

    if not isinstance(connector, ConnectorDef):
        return UNIT
    if connector.slug in RECORDED_FIXTURES and shown_verification(connector) != "live":
        return CONTRACT
    return proof_from_verification(shown_verification(connector))


def proof_for_qualified(qualified_name: str) -> str:
    """Proof for one tool. Connector tools follow the connector. Others are unit."""
    if not qualified_name.startswith("connectors."):
        return UNIT
    from ar_domain.connectors.catalog import tool_by_name  # noqa: PLC0415

    found = tool_by_name(qualified_name.split(".", 1)[1])
    if found is None:
        return UNIT
    return connector_proof(found[0])


def offered_to_model(
    qualified_name: str, store: object | None = None, tenant_id: object | None = None
) -> bool:
    """Whether the model may see this tool.

    Proof (``live``, ``contract``, ``unit``) is a badge. A connector tool is
    offered only when this tenant has the connector installed and a credential
    stored. Retired ``sandbox.*`` tools are not offered. Other built-ins stay
    offered; their label is still ``unit`` (OQ-123).
    """
    if qualified_name.startswith("sandbox."):
        return False
    if not qualified_name.startswith("connectors."):
        return True
    if store is None or tenant_id is None:
        return False
    return _connector_ready(store, tenant_id, qualified_name)


def _connector_ready(  # noqa: PLR0911, PLR0912
    store: object, tenant_id: object, qualified_name: str
) -> bool:
    """True when this tenant installed the connector and stored a credential."""
    from ar_domain.connectors.catalog import tool_by_name  # noqa: PLC0415

    short = qualified_name.split(".", 1)[1]
    found = tool_by_name(short)
    if found is None:
        return False
    connector, tool = found
    installs = getattr(store, "connector_installs", None)
    if not isinstance(installs, dict):
        return False
    install: dict[str, object] | None = None
    for row in installs.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("tenant_id")) != str(tenant_id):
            continue
        if str(row.get("slug")) != connector.slug or str(row.get("status")) != "installed":
            continue
        disabled = row.get("disabled_tools")
        if isinstance(disabled, list) and tool.name in {str(item) for item in disabled}:
            return False
        install = row
        break
    if install is None or not str(install.get("connection_name") or "").strip():
        return False
    name = str(install.get("connection_name")).lower()
    connections = getattr(store, "service_connections", None)
    if not isinstance(connections, dict):
        return False
    for row in connections.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("tenant_id")) != str(tenant_id):
            continue
        if str(row.get("name") or "").lower() != name:
            continue
        return _credential_live(row)
    return False


def _credential_live(row: dict[str, object]) -> bool:
    """A stored client secret is not a connection. The status has to say it is live."""
    status = str(row.get("status") or "").lower()
    if status in {"pending", "error", "errored", "expired", "revoked", "disabled"}:
        return False
    kind = str(row.get("kind") or "")
    if kind.startswith("oauth"):
        return bool(row.get("access_token") or row.get("refresh_token")) and status in {
            "active",
            "connected",
            "installed",
            "",
        }
    if status not in {"active", "connected", "installed", ""}:
        return False
    return bool(row.get("access_token") or row.get("refresh_token") or row.get("secret"))


def omitted_from_matrix(qualified_name: str) -> bool:
    """True for tools Stage 2 moves out of core. They are not listed as core."""
    if qualified_name in _OMITTED_NAMES:
        return True
    return qualified_name.startswith(_OMITTED_PREFIXES)


def matrix_path() -> Path:
    """The committed matrix. CI fails when this file differs from the generator."""
    return _repo_root() / "docs" / "09-plan" / "capability-matrix.md"


def render_capability_matrix() -> str:
    """One markdown table of capabilities, connectors, and tools."""
    lines = [
        "# Capability matrix",
        "",
        "Generated by `scripts/check_capability_matrix.py`. Do not edit by hand.",
        "Proof labels are `unit`, `contract`, and `live` "
        "([ADR-0032](../02-architecture/adr/ADR-0032-proof-labels.md)).",
        "A mock is not `live`. Offered is `yes` only when the model may call the tool.",
        "Twenty-one connectors have catalogue verification `not_live`. "
        "Proof is a badge. A connector tool is offered only after this tenant "
        "installs it and stores a credential, so the static matrix marks them no.",
        "Self-serve signup is not a route.",
        "Tools that Stage 2 moves into a pack are omitted. They are not core capabilities.",
        "",
        "| Kind | Name | Proof | Offered | Note |",
        "|---|---|---|---|---|",
    ]
    for name, proof, offered, note in _CAPABILITIES:
        lines.append(_row("capability", name, proof, offered, note))
    lines.extend(_row(*item) for item in _connector_rows())
    lines.extend(_row(*item) for item in _builtin_rows())
    lines.append("")
    return "\n".join(lines)


def _connector_rows() -> list[tuple[str, str, str, str, str]]:
    from ar_domain.connectors.catalog import CONNECTORS  # noqa: PLC0415

    rows: list[tuple[str, str, str, str, str]] = []
    for connector in CONNECTORS:
        proof = connector_proof(connector)
        note = _connector_note(connector.verification, proof)
        rows.append(("connector", connector.slug, proof, "no", note))
        rows.extend(
            (
                "connector-tool",
                tool.name,
                proof,
                "no",
                "Badge only. Offered after this tenant installs it and stores a credential.",
            )
            for tool in connector.tools
        )
    return rows


def _connector_note(verification: str, proof: str) -> str:
    if verification == "live":
        return "Catalogue verification is live."
    if verification == "public":
        return "Catalogue verification is public. Proof is contract, not live."
    return f"Catalogue verification is not_live. Proof is {proof}."


def _builtin_rows() -> list[tuple[str, str, str, str, str]]:
    from ar_domain.chat.service import ChatService  # noqa: PLC0415
    from ar_domain.tools import seed_tools  # noqa: PLC0415

    store = ChatService()
    seed_tools.seed(store, tenant=False)
    rows: list[tuple[str, str, str, str, str]] = []
    for version in store.tool_versions.values():
        if not isinstance(version, dict):
            continue
        name = str(version.get("qualified_name") or "")
        if not name or name.startswith("connectors.") or omitted_from_matrix(name):
            continue
        proof = proof_for_qualified(name)
        offered = "yes" if offered_to_model(name) else "no"
        note = "In-process tool. Not a recorded live model run."
        if name.startswith("sandbox."):
            note = (
                "Retired. A sandbox binding is rewritten to general "
                "and the model is not shown this tool."
            )
        rows.append(("tool", name, proof, offered, note))
    rows.sort(key=lambda item: item[1])
    return rows


def _row(kind: str, name: str, proof: str, offered: str, note: str) -> str:
    if proof not in LABELS:
        raise ValueError(f"unknown proof label {proof}")
    return f"| {kind} | `{name}` | `{proof}` | {offered} | {note} |"


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "docs" / "09-plan").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()
