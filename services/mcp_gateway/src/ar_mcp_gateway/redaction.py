"""PII redaction for tool results. Spec: docs/06-security/data-protection.md §5."""

from ar_domain.pii.analyzer import redact

__all__ = ["redact"]
