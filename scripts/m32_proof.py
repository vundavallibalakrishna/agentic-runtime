"""Live proof for M32. Reads AR_CERT_LLM_API_KEY and does not print it.

Runs the library check and compare path that the HTTP endpoints call, against
Qwen/Qwen3-32B on DeepInfra, plus the real Presidio profiles.
"""

from __future__ import annotations

import os
import sys
import uuid

from ar_domain.agents.access import Actor
from ar_domain.documents.library import DocumentLibrary
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.pii.analyzer import redact
from ar_domain.security.guardrails import apply_result_safety

POLICY = """# Access control

The annual picnic is on Friday in the courtyard.

Every employee completes a second login challenge before opening the production console.

Customer records stored on disk are encrypted with a key the company controls.

# Retention

Records stay in Ireland for 90 days under control P6.3.
"""

IRELAND = """# Transfers

Personal data is stored in Ireland.
"""

CAYMAN = """# Transfers

Personal data is stored in the Cayman Islands.
"""

MFA = "The organization requires multi-factor authentication for access to production systems."
MARS = "The organization operates a permanent colony on Mars."
MODEL = "Qwen/Qwen3-32B"
URL = "https://api.deepinfra.com/v1/openai/chat/completions"


class _Store:
    def __init__(self, key: str) -> None:
        self.scanner = "none"
        self.audit_log: list[dict[str, object]] = []
        self.tenant_settings: dict[uuid.UUID, dict[str, object]] = {}
        self._key = key

    def _completion_call(
        self, tenant_id: uuid.UUID, alias: str = "reasoning"
    ) -> tuple[str, dict[str, str], float, bool]:
        del tenant_id, alias
        return MODEL, {"Authorization": f"Bearer {self._key}"}, 120.0, True

    def _completion_url_for(self, tenant_id: uuid.UUID, alias: str, headers: dict[str, str]) -> str:
        del tenant_id, alias
        headers["Authorization"] = f"Bearer {self._key}"
        return URL


def _row(report: dict[str, object], index: int) -> dict[str, object]:
    rows = report.get("rows")
    if not isinstance(rows, list) or index >= len(rows) or not isinstance(rows[index], dict):
        raise SystemExit(f"missing row {index}")
    row = rows[index]
    return {str(key): value for key, value in row.items()}


def main() -> int:
    key = os.environ.get("AR_CERT_LLM_API_KEY", "").strip()
    sample = "Records stay in Ireland for 90 days under control P6.3."
    kept = redact(sample, profile="analysis")
    outbound = redact(sample, profile="outbound")
    print("analysis_profile", kept)
    print("outbound_profile", outbound)
    if "Ireland" not in kept or "90 days" not in kept or "P6.3" not in kept:
        print("FAIL analysis profile masked evidence")
        return 1
    if "Ireland" in outbound or "90 days" in outbound or "P6.3" in outbound:
        print("FAIL outbound profile did not mask evidence")
        return 1
    if not key:
        print("LIVE_PROOF NOT VERIFIED")
        return 0

    tenant = uuid.uuid4()
    actor = Actor(tenant_id=tenant, user_id=uuid.uuid4(), permissions=PERMISSION_KEYS)
    store = _Store(key)
    library = DocumentLibrary(store)
    policy = library.ingest(actor, data=POLICY.encode(), filename="acme-policy.md")
    ireland = library.ingest(actor, data=IRELAND.encode(), filename="dpa-ireland.md")
    cayman = library.ingest(actor, data=CAYMAN.encode(), filename="dpa-cayman.md")
    checked = library.check(
        actor,
        uuid.UUID(str(policy["id"])),
        requirements=[MFA, MARS],
        label="M32",
    )
    met = _row(checked, 0)
    missing = _row(checked, 1)
    raw_citation = met.get("citation")
    quote = ""
    if isinstance(raw_citation, dict):
        quote = str(raw_citation.get("quote") or "")
    print("mfa_verdict", met.get("verdict"))
    print("mfa_quote", quote)
    print("mars_verdict", missing.get("verdict"))
    print("mars_citation", missing.get("citation"))
    compared = library.compare(actor, uuid.UUID(str(ireland["id"])), uuid.UUID(str(cayman["id"])))
    changes = compared.get("changes")
    blob = str(changes)
    visible, _flag = apply_result_safety(
        store, blob, open_world=True, analysis=True, tenant_id=tenant
    )
    print("compare_has_ireland", "Ireland" in visible)
    print("compare_has_cayman", "Cayman" in visible)
    print("compare_location_tokens", visible.count("[LOCATION]"))
    ok = (
        met.get("verdict") == "met"
        and "login challenge" in quote
        and "picnic" not in quote.lower()
        and missing.get("verdict") == "not_found"
        and missing.get("citation") is None
        and "Ireland" in visible
        and "Cayman" in visible
        and "[LOCATION]" not in visible
    )
    print("LIVE_PROOF", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
