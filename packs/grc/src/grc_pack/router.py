"""HTTP for an enabled GRC pack."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ar_api.deps import require_permission
from ar_contracts.api_model import ApiModel

router = APIRouter()


class CatalogueBody(ApiModel):
    name: str
    csv: str


class LinkBody(ApiModel):
    item_id: uuid.UUID
    evidence_id: uuid.UUID
    note: str = ""


class RiskBody(ApiModel):
    title: str
    score: int = Field(ge=0, le=100)
    status: str = "open"


class FindingBody(ApiModel):
    title: str
    item_key: str = ""
    status: str = "open"


class JudgeBody(ApiModel):
    passages: list[dict[str, Any]] = Field(default_factory=list)


def _enabled(request: Request) -> None:
    from ar_api.routers.tooling import actor, chat  # noqa: PLC0415
    from ar_common.errors import ArError, ErrorCode  # noqa: PLC0415
    from ar_domain.packs.registry import tenant_packs  # noqa: PLC0415

    who = actor(request)
    enabled = any(
        row.get("pack_id") == "grc" and row.get("enabled")
        for row in tenant_packs(chat(request), who)
    )
    if not enabled:
        raise ArError(ErrorCode.NOT_FOUND, "feature_disabled")


@router.post(
    "/api/v1/ext/grc/catalogues",
    dependencies=[Depends(_enabled), Depends(require_permission("grc.catalogues:manage"))],
)
async def import_catalogue(body: CatalogueBody, request: Request) -> dict[str, object]:
    from ar_api.routers.tooling import actor, chat  # noqa: PLC0415
    from grc_pack.book import CatalogueBook  # noqa: PLC0415

    return CatalogueBook(chat(request)).import_csv(actor(request), body.name, body.csv)


@router.post(
    "/api/v1/ext/grc/evidence-links",
    dependencies=[Depends(_enabled), Depends(require_permission("grc.evidence:link"))],
)
async def link_evidence(body: LinkBody, request: Request) -> dict[str, object]:
    from ar_api.routers.tooling import actor, chat  # noqa: PLC0415
    from grc_pack.book import CatalogueBook  # noqa: PLC0415

    return CatalogueBook(chat(request)).link_evidence(
        actor(request), body.item_id, body.evidence_id, body.note
    )


@router.post(
    "/api/v1/ext/grc/risks",
    dependencies=[Depends(_enabled), Depends(require_permission("grc.risks:manage"))],
)
async def add_risk(body: RiskBody, request: Request) -> dict[str, object]:
    from ar_api.routers.tooling import actor, chat  # noqa: PLC0415
    from grc_pack.book import CatalogueBook  # noqa: PLC0415

    return CatalogueBook(chat(request)).add_risk(
        actor(request), body.title, body.score, body.status
    )


@router.post(
    "/api/v1/ext/grc/findings",
    dependencies=[Depends(_enabled), Depends(require_permission("grc.findings:manage"))],
)
async def add_finding(body: FindingBody, request: Request) -> dict[str, object]:
    from ar_api.routers.tooling import actor, chat  # noqa: PLC0415
    from grc_pack.book import CatalogueBook  # noqa: PLC0415

    return CatalogueBook(chat(request)).add_finding(
        actor(request), body.title, body.item_key, body.status
    )


@router.post(
    "/api/v1/ext/grc/catalogues/{catalogue_id}:judge",
    dependencies=[Depends(_enabled), Depends(require_permission("grc.catalogues:manage"))],
)
async def judge(catalogue_id: uuid.UUID, body: JudgeBody, request: Request) -> dict[str, object]:
    from ar_api.routers.tooling import actor, chat  # noqa: PLC0415
    from grc_pack.book import CatalogueBook  # noqa: PLC0415

    rows = CatalogueBook(chat(request)).judge(actor(request), catalogue_id, body.passages)
    return {"judgements": rows}
