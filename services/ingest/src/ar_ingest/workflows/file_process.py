"""File processing decisions. Spec: docs/03-specs/13-files-artifacts.md.

The activity is idempotent: the same bytes and scanner always yield the same status.
"""

from ar_domain.files.logic import scan_bytes


def process_upload(data: bytes, *, scanner: str) -> dict[str, str]:
    """Return status and scan_status for an uploaded object."""
    verdict = scan_bytes(data, scanner=scanner)
    if verdict == "infected":
        return {"status": "quarantined", "scan_status": "infected"}
    if verdict == "skipped":
        return {"status": "ready", "scan_status": "skipped"}
    return {"status": "ready", "scan_status": "clean"}


def thumbnail_png() -> bytes:
    """1x1 PNG used when pillow is not installed in the unit environment."""
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\xef\x00\x00\x00\x00IEND\xaeB`\x82"
    )
