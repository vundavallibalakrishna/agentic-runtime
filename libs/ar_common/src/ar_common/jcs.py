"""JSON Canonicalization Scheme (RFC 8785) and approval argument hashes.

Spec: docs/02-architecture/adr/ADR-0015-approval-args-hash.md,
docs/05-contracts/api-conventions.md.
"""

import hashlib
from typing import TYPE_CHECKING

import rfc8785

if TYPE_CHECKING:
    from pydantic import JsonValue


def canonical_json(value: JsonValue) -> bytes:
    """Return the RFC 8785 canonical encoding of a JSON value."""
    encoded = rfc8785.dumps(value)
    return encoded if isinstance(encoded, bytes) else encoded.encode()


def args_hash(value: JsonValue) -> str:
    """Return the hex SHA-256 of the canonical JSON encoding."""
    return hashlib.sha256(canonical_json(value)).hexdigest()
