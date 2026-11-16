"""Outbound clients are imported only where the egress check runs.

The check follows imports, aliases, ``importlib`` and ``getattr``. Mentioning
a companion name does not make a raw client legal. ``httpx`` itself stays
importable for ``Response`` and ``HTTPError``; constructing a client is not.
"""

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
_APPROVED = {
    Path("libs/ar_common/src/ar_common/egress_http.py"),
    Path("libs/ar_common/src/ar_common/s3.py"),
    Path("libs/ar_common/src/ar_common/telemetry.py"),
    Path("libs/ar_domain/src/ar_domain/connectors/storage.py"),
    Path("libs/ar_domain/src/ar_domain/connectors/mail.py"),
    Path("libs/ar_domain/src/ar_domain/connectors/dispatch.py"),
    Path("libs/ar_domain/src/ar_domain/notifications/smtp_mail.py"),
    Path("libs/ar_domain/src/ar_domain/identity/mail.py"),
    Path("libs/ar_domain/src/ar_domain/tools/database.py"),
    Path("services/channels/src/ar_channels/email_channel.py"),
}
_MODULES = {
    "httpx": {
        "Client",
        "AsyncClient",
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "request",
        "stream",
        "HTTPTransport",
        "AsyncHTTPTransport",
    },
    "requests": {"get", "post", "put", "patch", "delete", "head", "request", "Session"},
    "urllib.request": {"urlopen"},
    "http.client": {"HTTPConnection", "HTTPSConnection"},
    "aiohttp": {"ClientSession"},
    "boto3": {"client", "resource", "Session"},
    "smtplib": {"SMTP", "SMTP_SSL"},
    "imaplib": {"IMAP4", "IMAP4_SSL"},
    "aiosmtplib": {"SMTP"},
    "aioimaplib": {"IMAP4"},
    "psycopg": {"connect"},
    "pymysql": {"connect"},
    "socket": {"create_connection"},
    "asyncio": {"open_connection"},
}


def test_outbound_clients_are_pinned() -> None:
    offenders: list[str] = []
    for root in _ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if _SKIP.intersection(path.parts) or path in _APPROVED:
                continue
            offenders.extend(_file(path))
    assert offenders == []


def test_the_bypass_forms_are_flagged() -> None:
    sample = Path(__file__).with_name("_egress_evil.py")
    flagged = {int(item.rsplit(":", 1)[1]) for item in _file(sample)}
    missed = [
        line.strip()
        for number, line in enumerate(sample.read_text(encoding="utf-8").splitlines(), start=1)
        if line.strip().startswith("return ") and number not in flagged
    ]
    assert missed == []


def _file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bindings, modules = _bindings(tree)
    return [
        f"{path}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _forbidden(node, bindings, modules)
    ]


def _bindings(tree: ast.AST) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    """Names that point at a forbidden constructor, and imported module names."""
    names: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = (alias.asname or alias.name).split(".", 1)[0]
                modules[root] = alias.name.split(".", 1)[0]
                if "." in alias.name:
                    modules[alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                if node.module in _MODULES and alias.name in _MODULES[node.module]:
                    names[local] = (node.module, alias.name)
    body = getattr(tree, "body", [])
    for node in body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                bound = _constructor(node.value, names, modules)
                if bound is not None:
                    names[target.id] = bound
    return names, modules


def _forbidden(
    call: ast.Call, bindings: dict[str, tuple[str, str]], modules: dict[str, str]
) -> bool:
    if isinstance(call.func, ast.Call) and isinstance(call.func.func, ast.Name):
        if call.func.func.id == "getattr" and len(call.func.args) >= 2:
            owner = _dotted(call.func.args[0], modules, bindings)
            name = call.func.args[1]
            if owner and isinstance(name, ast.Constant) and _match(f"{owner}.{name.value}"):
                return True
    dotted = _dotted(call.func, modules, bindings)
    if dotted is not None and _match(dotted):
        return True
    if isinstance(call.func, ast.Attribute) and call.func.attr in {"client", "resource", "Client"}:
        return _constructor(call.func.value, bindings, modules) is not None
    if isinstance(call.func, ast.Call) and _loads_forbidden(call.func):
        return True
    return False


def _dotted(
    node: ast.AST, modules: dict[str, str], bindings: dict[str, tuple[str, str]]
) -> str | None:
    if isinstance(node, ast.Name):
        if node.id in bindings:
            module, attr = bindings[node.id]
            return f"{module}.{attr}" if attr else module
        return modules.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        parent = _dotted(node.value, modules, bindings)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def _match(dotted: str) -> bool:
    for module, attrs in _MODULES.items():
        prefix = f"{module}."
        if dotted == module or dotted.startswith(prefix):
            rest = dotted[len(prefix) :] if dotted.startswith(prefix) else ""
            head = rest.split(".", 1)[0]
            if head in attrs or dotted == module:
                return head in attrs
    return False


def _constructor(
    node: ast.AST, bindings: dict[str, tuple[str, str]], modules: dict[str, str]
) -> tuple[str, str] | None:
    if isinstance(node, ast.Name):
        if node.id in bindings:
            return bindings[node.id]
        module = modules.get(node.id)
        if module in _MODULES:
            return module, ""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Call):
        if _loads_forbidden(node.value):
            return "httpx", node.attr
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        module = modules.get(node.value.id, node.value.id)
        if module in _MODULES and node.attr in _MODULES[module]:
            return module, node.attr
        bound = bindings.get(node.value.id)
        if bound is not None and node.attr in {"client", "resource", "Client"}:
            return bound[0], node.attr
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            owner = _constructor(node.args[0], bindings, modules)
            if owner is not None and str(node.args[1].value) in _MODULES.get(owner[0], set()):
                return owner[0], str(node.args[1].value)
    if isinstance(node, ast.Call) and _loads_forbidden(node):
        return "httpx", "Client"
    return None


def _loads_forbidden(node: ast.Call) -> bool:
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "import_module":
        return False
    if not node.args or not isinstance(node.args[0], ast.Constant):
        return False
    return str(node.args[0].value) in _MODULES
