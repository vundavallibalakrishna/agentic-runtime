"""Sandbox path, egress and lifecycle rules shared by the agent and the API.

Spec: docs/03-specs/12-sandbox-manager.md. The dev API keeps chat in process
memory (OQ-31); these functions are the rules both that path and the container
agent apply.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_TMP = "/" + "tmp"

DEFAULT_DENY_CIDRS: tuple[str, ...] = (
    "169.254.169.254/32",
    "169.254.0.0/16",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "::1/128",
    "fc00::/7",
    "100.64.0.0/10",
)
STDOUT_LIMIT = 16 * 1024
STDERR_LIMIT = 8 * 1024
_DIGEST = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_ENV_KEY = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_SECRET_HINT = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)")
_CURL = re.compile(r"https?://([^/\s'\"]+)")
_PACKAGE = re.compile(r"(?:^|[;&|]\s*)(?:pip3?|npm|pnpm|apt-get|apt)\s+install\b")
_TRANSITIONS: dict[tuple[str, str], str] = {
    ("", "ensure"): "pending",
    ("pending", "create"): "starting",
    ("starting", "health"): "ready",
    ("starting", "fail"): "failed",
    ("ready", "touch"): "ready",
    ("ready", "suspend"): "suspending",
    ("suspending", "stop"): "suspended",
    ("suspended", "ensure"): "resuming",
    ("resuming", "health"): "ready",
    ("ready", "terminate"): "terminating",
    ("suspended", "terminate"): "terminating",
    ("failed", "ensure"): "pending",
    ("terminating", "stop"): "terminated",
}


class PathEscapeError(ValueError):
    """A path left the sandbox workspace or temporary directory."""


def transition(status: str, event: str) -> str:
    """Return the next lifecycle status. Unknown pairs fail closed."""
    try:
        return _TRANSITIONS[(status, event)]
    except KeyError as exc:
        raise ValueError(f"cannot {event} a sandbox that is {status or 'missing'}") from exc


def confine(root: Path, raw: str) -> Path:
    """Resolve ``raw`` under ``/workspace`` or ``/tmp`` inside ``root``.

    Symlinks that escape the chosen root are rejected. ``root`` is the sandbox
    directory that contains ``workspace`` and ``tmp``.
    """
    text = raw or "/workspace"
    if text.startswith(_TMP):
        base = (root / "tmp").resolve()
        relative = text.removeprefix(_TMP).lstrip("/")
    elif text == "/workspace" or text.startswith("/workspace/"):
        base = (root / "workspace").resolve()
        relative = text.removeprefix("/workspace").lstrip("/")
    else:
        raise PathEscapeError("path is outside the computer")
    base.mkdir(parents=True, exist_ok=True)
    current = base
    for part in Path(relative).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise PathEscapeError("path is outside the computer")
        current = current / part
        if current.is_symlink():
            target = current.resolve()
            if not target.is_relative_to(base):
                raise PathEscapeError("symlink escapes the computer")
            current = target
    resolved = current.resolve() if current.exists() else current
    if current.exists() and not resolved.is_relative_to(base):
        raise PathEscapeError("path is outside the computer")
    return current


def virtual_path(root: Path, path: Path) -> str:
    """Show a host path as ``/workspace/...`` or ``/tmp/...``."""
    workspace = (root / "workspace").resolve()
    temporary = (root / "tmp").resolve()
    resolved = path.resolve() if path.exists() else path
    if resolved.is_relative_to(workspace):
        suffix = resolved.relative_to(workspace).as_posix()
        return "/workspace" if not suffix else f"/workspace/{suffix}"
    if resolved.is_relative_to(temporary):
        suffix = resolved.relative_to(temporary).as_posix()
        return _TMP if not suffix else f"{_TMP}/{suffix}"
    raise PathEscapeError("path is outside the computer")


def truncate_output(stdout: bytes, stderr: bytes) -> tuple[str, str, bool]:
    """Keep the last 16 KiB of stdout and 8 KiB of stderr."""
    truncated = len(stdout) > STDOUT_LIMIT or len(stderr) > STDERR_LIMIT
    out = stdout[-STDOUT_LIMIT:].decode("utf-8", errors="replace")
    err = stderr[-STDERR_LIMIT:].decode("utf-8", errors="replace")
    return out, err, truncated


def clean_env(supplied: dict[str, str] | None) -> dict[str, str]:
    """Keep a small environment. Secret-shaped keys are dropped."""
    base = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/home/sandbox", "LANG": "C.UTF-8"}
    for key, value in (supplied or {}).items():
        if not _ENV_KEY.match(key) or _SECRET_HINT.search(key):
            continue
        base[key] = value
    return base


def package_install(command: str) -> bool:
    """True when the command installs packages."""
    return _PACKAGE.search(command) is not None


def curl_host(command: str) -> str | None:
    """Return the host of the first URL in a curl or wget command."""
    stripped = command.strip()
    if not stripped.startswith(("curl", "wget")):
        return None
    match = _CURL.search(stripped)
    if match is None:
        return None
    return match.group(1).split(":")[0].lower()


def digest_pinned(image_ref: str, registries: tuple[str, ...]) -> str | None:
    """Return an error when the image is not a digest from an allowed registry."""
    if not _DIGEST.match(image_ref):
        return "image must be pinned to a sha256 digest"
    allowed = tuple(item.rstrip("/") for item in registries if item)
    if not any(image_ref.startswith(f"{prefix}/") for prefix in allowed):
        return "image registry is not allowed"
    return None


def allowed_hosts(
    template: list[str],
    extra: list[str],
    tenant: list[str],
    *,
    mirrors: list[str],
    allow_packages: bool,
    env: str,
) -> list[str]:
    """Compute the egress allowlist. ``*`` is dropped in production."""
    merged: list[str] = []
    for host in [*template, *extra]:
        name = host.strip().lower()
        if not name or name in merged:
            continue
        if name == "*" and env == "prod":
            continue
        merged.append(name)
    if tenant:
        permitted = {item.strip().lower() for item in tenant if item.strip()}
        merged = [host for host in merged if host in permitted]
    if allow_packages:
        for host in mirrors:
            name = host.strip().lower()
            if name and name not in merged and not (name == "*" and env == "prod"):
                merged.append(name)
    return merged


def ip_denied(address: str, cidrs: tuple[str, ...] | list[str]) -> bool:
    """True when ``address`` falls in a denied network."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    for item in cidrs:
        try:
            network = ipaddress.ip_network(item, strict=False)
        except ValueError:
            continue
        if ip in network:
            return True
    return False


def host_denied(
    host: str,
    cidrs: tuple[str, ...] | list[str],
    resolve: Callable[[str], list[str]],
    *,
    allow_loopback: bool = False,
) -> bool:
    """Deny a host when it is a blocked address or resolves to one.

    Resolution failure is a deny. Loopback can be opened for the local test site
    when the process is not production.
    """
    active = tuple(item for item in cidrs if not (allow_loopback and item == "127.0.0.0/8"))
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            addresses = resolve(host)
        except OSError:
            return True
    if not addresses:
        return True
    return any(ip_denied(item, active) for item in addresses)


def parse_warm_pool(spec: str) -> dict[str, int]:
    """Parse ``default=4,browser=2`` into counts."""
    found: dict[str, int] = {}
    for part in spec.split(","):
        if "=" not in part:
            continue
        name, raw = part.split("=", 1)
        slug = name.strip()
        if not slug:
            continue
        try:
            found[slug] = max(0, int(raw.strip()))
        except ValueError:
            continue
    return found


def download_headers(name: str, mime: str, *, inline: bool) -> dict[str, str]:
    """Attachment headers. HTML and SVG never render inline."""
    dangerous = mime in {"text/html", "image/svg+xml", "application/xhtml+xml"}
    safe_types = {"application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif"}
    safe_inline = inline and not dangerous and mime in safe_types
    media = "application/octet-stream" if dangerous else mime
    disposition = "inline" if safe_inline else "attachment"
    cleaned = name.replace('"', "") or "download"
    return {
        "Content-Type": media,
        "Content-Disposition": f'{disposition}; filename="{cleaned}"',
        "Content-Security-Policy": "sandbox",
        "X-Content-Type-Options": "nosniff",
    }


def sanitise_name(name: str) -> str:
    """Artifact names keep letters, numbers, spaces, dots and dashes."""
    cleaned = re.sub(r"[^\w.\- ]", "_", name, flags=re.ASCII).strip() or "artifact"
    return cleaned[:120]


def csv_rows(data: bytes, *, limit: int = 1000) -> list[list[str]]:
    """First ``limit`` rows of a CSV file, including the header."""
    text = data.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows: list[list[str]] = []
    for index, row in enumerate(reader):
        if index >= limit:
            break
        rows.append([cell[:200] for cell in row])
    return rows


_XLSX = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def xlsx_rows(data: bytes, *, limit: int = 1000) -> list[list[str]]:
    """First ``limit`` rows of the first worksheet. A bad workbook is an empty preview."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            shared = _shared_strings(book)
            sheet = book.read("xl/worksheets/sheet1.xml")
    except KeyError, zipfile.BadZipFile, ET.ParseError:
        return []
    try:
        root = ET.fromstring(sheet)  # noqa: S314
    except ET.ParseError:
        return []
    rows: list[list[str]] = []
    for index, row in enumerate(root.iter(f"{_XLSX}row")):
        if index >= limit:
            break
        cells: list[str] = []
        for cell in row.findall(f"{_XLSX}c"):
            kind = cell.attrib.get("t")
            value = cell.find(f"{_XLSX}v")
            raw = "" if value is None or value.text is None else value.text
            if kind == "s" and raw.isdigit():
                pointer = int(raw)
                raw = shared[pointer] if pointer < len(shared) else raw
            cells.append(raw[:200])
        rows.append(cells)
    return rows


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        payload = book.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(payload)  # noqa: S314
    return ["".join(node.itertext()) for node in root.findall(f"{_XLSX}si")]


def png_chart(values: list[int], *, labels: list[str] | None = None) -> bytes:
    """A small bar chart PNG with no third-party library."""
    del labels
    width, height = 480, 240
    series = values or [0]
    peak = max(series) or 1
    margin = 16
    slot = max(1, (width - margin * 2) // len(series))
    rows: list[bytes] = []
    for y in range(height):
        pixel = bytearray()
        for x in range(width):
            ink = _bar(x, y, series, peak=peak, slot=slot, margin=margin, height=height)
            pixel.extend(ink)
        rows.append(b"\x00" + bytes(pixel))
    return _png(width, height, b"".join(rows))


def _bar(
    x: int,
    y: int,
    series: list[int],
    *,
    peak: int,
    slot: int,
    margin: int,
    height: int,
) -> bytes:
    if x < margin or x >= margin + slot * len(series) or y > height - margin:
        return b"\xf4\xf1\xec"
    index = min((x - margin) // slot, len(series) - 1)
    local = (x - margin) % slot
    bar_height = int(series[index] / peak * (height - margin * 3))
    top = height - margin - bar_height
    if 4 < local < slot - 4 and top <= y <= height - margin:
        return b"\x1f\x6f\x68"
    return b"\xf4\xf1\xec"


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


class _Tree(HTMLParser):
    """Collect interactive elements in document order."""

    def __init__(self) -> None:
        super().__init__()
        self.items: list[dict[str, str]] = []
        self._buffer: list[str] = []
        self.title = ""
        self._in_title = False
        self._text_for: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
            self._buffer = []
        if tag in {"a", "button", "input", "textarea", "select", "h1", "h2", "p"}:
            self.items.append(
                {
                    "tag": tag,
                    "name": data.get("name") or data.get("aria-label") or data.get("id") or tag,
                    "href": data.get("href", ""),
                    "type": data.get("type", ""),
                    "value": data.get("value", ""),
                }
            )
            if tag in {"a", "button", "textarea", "h1", "h2", "p"}:
                self._text_for = len(self.items) - 1
                self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._in_title:
            self.title = "".join(self._buffer).strip()
            self._in_title = False
        if self._text_for is not None and tag == self.items[self._text_for]["tag"]:
            text = " ".join("".join(self._buffer).split())
            if text:
                self.items[self._text_for]["name"] = text
            self._text_for = None

    def handle_data(self, data: str) -> None:
        if self._in_title or self._text_for is not None:
            self._buffer.append(data)


def accessibility_tree(
    html: str, *, max_chars: int = 40000
) -> tuple[str, str, list[dict[str, str]]]:
    """Return text with ``[ref=eN]`` markers, the title, and the element list."""
    parser = _Tree()
    parser.feed(html)
    lines = [f"title: {parser.title or 'page'}"]
    elements: list[dict[str, str]] = []
    for index, item in enumerate(parser.items, start=1):
        ref = f"e{index}"
        label = item["name"] or item["tag"]
        lines.append(f"[ref={ref}] {item['tag']} {label}".strip())
        elements.append({**item, "ref": ref})
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars]
    return text, parser.title, elements


def helper_verdict(status: int) -> str:
    """Squid external-acl result. Anything other than 200 is a deny."""
    return "OK" if status == 200 else "ERR"
