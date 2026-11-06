"""File access, MIME allow-list and scan decisions. Spec: docs/03-specs/13-files-artifacts.md."""

import mimetypes
from collections.abc import Mapping
from dataclasses import dataclass

from ar_contracts.tenants import READABLE_UPLOAD_MIME_TYPES

# The most the product keeps for one file today, whatever a tenant sets: file bytes live
# in the database until M38b-T13 moves them to the object store.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
# What a route that takes a file accepts as a request body: the cap plus the multipart
# envelope. The tenant's own cap (``upload_rules``) is applied to the file by ``upload``.
# The web app's proxy buffers the same amount (``proxyClientMaxBodySize`` in next.config).
UPLOAD_BODY_LIMIT = MAX_UPLOAD_BYTES + 64 * 1024
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@dataclass(frozen=True, slots=True)
class FileView:
    """Access-check projection of a file row."""

    tenant_id: str
    owner_user_id: str | None
    conversation_id: str | None
    status: str


def object_key(tenant_id: str, kind: str, year: str, month: str, file_id: str) -> str:
    """Storage key ``t/{tenant}/{kind}/{yyyy}/{mm}/{id}``."""
    return f"t/{tenant_id}/{kind}/{year}/{month}/{file_id}"


def upload_rules(settings: Mapping[str, object]) -> UploadRules:
    """What a tenant lets its people attach: its ``security`` settings, within the product's cap."""
    security = settings.get("security")
    section = security if isinstance(security, Mapping) else {}
    listed = section.get("allowed_upload_mime_types")
    types = (
        tuple(str(item).lower() for item in listed if str(item).strip())
        if isinstance(listed, list)
        else READABLE_UPLOAD_MIME_TYPES
    )
    raw = section.get("max_upload_mb")
    megabytes = raw if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0 else 25
    return UploadRules(
        mime_types=tuple(sorted(set(types))),
        max_bytes=min(megabytes * 1024 * 1024, MAX_UPLOAD_BYTES),
    )


@dataclass(frozen=True, slots=True)
class UploadRules:
    """The types a person may attach and the largest file, as the tenant has them."""

    mime_types: tuple[str, ...]
    max_bytes: int

    def allows(self, mime_type: str) -> bool:
        return mime_type.lower() in self.mime_types


def typed_by_name(name: str, mime_type: str) -> str:
    """The file's type, from its name when the browser gave none or a meaningless one."""
    stated = (mime_type or "").strip().lower()
    if stated and stated != "application/octet-stream":
        return stated
    guessed, _encoding = mimetypes.guess_type(name)
    return guessed or stated


def mime_allowed(mime_type: str) -> bool:
    """Whether the product can read this type at all."""
    return mime_type.lower() in READABLE_UPLOAD_MIME_TYPES


def scan_bytes(data: bytes, *, scanner: str) -> str:
    """Return ``clean``, ``skipped`` or ``infected``.

    ``scanner='none'`` skips. ``clamav`` (and any injected scanner name other
    than ``none``) quarantines the EICAR test string.
    """
    if scanner == "none":
        return "skipped"
    if EICAR in data:
        return "infected"
    return "clean"


def can_read_file(
    file: FileView,
    *,
    tenant_id: str,
    user_id: str,
    conversation_owner: bool,
    read_all: bool,
) -> bool:
    """Owner, conversation owner, or a privileged reader."""
    if file.tenant_id != tenant_id or file.status == "deleted":
        return False
    if read_all or file.owner_user_id == user_id:
        return True
    return conversation_owner and file.conversation_id is not None
