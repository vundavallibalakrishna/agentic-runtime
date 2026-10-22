"""File access, MIME allow-list and scan decisions. Spec: docs/03-specs/13-files-artifacts.md."""

from dataclasses import dataclass

ALLOWED_MIME = frozenset(
    {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/png",
        "image/jpeg",
        "image/webp",
    }
)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
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


def mime_allowed(mime_type: str) -> bool:
    return mime_type in ALLOWED_MIME


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
