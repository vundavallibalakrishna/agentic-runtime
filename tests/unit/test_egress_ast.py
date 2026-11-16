"""Every outbound client is the egress transport or calls the closed-mode pin."""

from __future__ import annotations

import ast
from pathlib import Path

_ROOTS = (
    Path("libs/ar_common/src"),
    Path("libs/ar_domain/src"),
    Path("libs/ar_contracts/src"),
    Path("services"),
    Path("connectors"),
    Path("packs"),
)
_SKIP = {"tests", "examples", "scripts"}
_ALLOWED_FILES = {
    Path("libs/ar_common/src/ar_common/egress_http.py"),
    Path("libs/ar_common/src/ar_common/host_ports.py"),
}
_COMPANIONS = {
    "approved_address",
    "pinned_host",
    "guard",
    "decide",
    "decide_url",
    "sync_client",
    "async_client",
    "_require_endpoint",
    "_pinned_endpoint",
    "_dial",
    "_client_kwargs",
}
_TARGETS = {
    ("httpx", "Client"),
    ("httpx", "AsyncClient"),
    ("httpx", "get"),
    ("httpx", "post"),
    ("httpx", "request"),
    ("httpx", "stream"),
    ("requests", "get"),
    ("requests", "post"),
    ("requests", "Session"),
    ("urllib.request", "urlopen"),
    ("aiohttp", "ClientSession"),
    ("boto3", "client"),
    ("smtplib", "SMTP"),
    ("smtplib", "SMTP_SSL"),
    ("imaplib", "IMAP4"),
    ("imaplib", "IMAP4_SSL"),
    ("aiosmtplib", "SMTP"),
    ("aioimaplib", "IMAP4"),
    ("socket", "socket"),
    ("aiobotocore", "create_client"),
    ("opentelemetry.exporter.otlp.proto.grpc.trace_exporter", "OTLPSpanExporter"),
    ("opentelemetry.exporter.otlp.proto.grpc.metric_exporter", "OTLPMetricExporter"),
}


def test_outbound_clients_are_pinned() -> None:
    offenders: list[str] = []
    for root in _ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if _SKIP.intersection(path.parts) or path in _ALLOWED_FILES:
                continue
            offenders.extend(_file(path))
    assert offenders == []


def _file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = _aliases(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = _target(node.func, aliases)
        if target not in _TARGETS:
            continue
        if not _companion(node, tree):
            found.append(f"{path}:{node.lineno}")
    return found


def _aliases(tree: ast.AST) -> dict[str, str]:
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                names[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name] = alias.name
    return names


def _target(func: ast.expr, aliases: dict[str, str]) -> tuple[str, str] | None:
    if isinstance(func, ast.Attribute) and func.attr == "create_client":
        return "aiobotocore", "create_client"
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        module = aliases.get(func.value.id, func.value.id)
        return module, func.attr
    if isinstance(func, ast.Name):
        full = aliases.get(func.id, "")
        if "." in full:
            module, name = full.rsplit(".", 1)
            return module, name
    return None


def _companion(call: ast.Call, tree: ast.AST) -> bool:
    owner = _enclosing(call, tree)
    if owner is None:
        return False
    for node in ast.walk(owner):
        if isinstance(node, ast.Name) and node.id in _COMPANIONS:
            return True
        if isinstance(node, ast.Attribute) and node.attr in _COMPANIONS:
            return True
    return False


def _enclosing(call: ast.Call, tree: ast.AST) -> ast.AST | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for child in ast.walk(node):
            if child is call:
                return node
    return None
