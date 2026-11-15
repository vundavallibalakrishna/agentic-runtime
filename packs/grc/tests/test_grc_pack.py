"""Catalogue import, evidence links, risks, findings and the document judge."""

from __future__ import annotations

import uuid
from pathlib import Path

from ar_domain.agents.access import Actor
from grc_pack import enable
from grc_pack.book import CatalogueBook
from grc_pack.tools import dispatch_grc
from records_pack.vault import EvidenceBook

_CSV = "key,title,statement\nD1,Door,The door stays locked after hours.\n"


def _actor() -> Actor:
    return Actor(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        permissions=frozenset(
            {
                "grc.catalogues:manage",
                "grc.evidence:link",
                "grc.risks:manage",
                "grc.findings:manage",
                "evidence:capture",
                "evidence:read",
            }
        ),
    )


def test_import_judge_link_risk_and_finding() -> None:
    from ar_testing.demo import demo_store

    store = demo_store()
    actor = _actor()
    enable(store, actor.tenant_id, owner=actor.user_id)
    book = CatalogueBook(store)
    imported = book.import_csv(actor, "House rules", _CSV)
    items = book.items(actor, uuid.UUID(str(imported["id"])))
    judgements = book.judge(
        actor,
        uuid.UUID(str(imported["id"])),
        [{"id": "p1", "text": "The door stays locked after hours. Visitors sign in."}],
    )
    assert judgements[0]["verdict"] == "supported"
    sealed = EvidenceBook(store).capture(actor, {"collection_method": "upload"}, b"photo")
    linked = book.link_evidence(actor, uuid.UUID(str(items[0]["id"])), uuid.UUID(str(sealed["id"])))
    assert linked["evidenceId"] == str(sealed["id"])
    risk = book.add_risk(actor, "Unlocked door", 40)
    finding = book.add_finding(actor, "No sign-in sheet", "D1")
    assert risk["score"] == 40
    assert finding["itemKey"] == "D1"
    args = {
        "_tenant_id": actor.tenant_id,
        "_user_id": actor.user_id,
        "title": "Late review",
        "score": 10,
    }
    added = dispatch_grc(store, "add_risk", args, "")
    assert added["is_error"] is False


def test_the_sql_migration_is_reversible_and_has_rls() -> None:
    root = Path(__file__).resolve().parents[1] / "migrations"
    up = (root / "0001_up.sql").read_text(encoding="utf-8")
    down = (root / "0001_down.sql").read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS grc_pack" in up
    assert "ENABLE ROW LEVEL SECURITY" in up
    assert "DROP SCHEMA IF EXISTS grc_pack CASCADE" in down
