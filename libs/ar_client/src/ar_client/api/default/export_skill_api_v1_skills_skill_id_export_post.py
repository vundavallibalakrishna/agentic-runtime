from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.export_skill_api_v1_skills_skill_id_export_post_response_export_skill_api_v1_skills_skill_id_export_post import (
    ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    skill_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/skills/{skill_id}:export".format(
            skill_id=quote(str(skill_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost.from_dict(
            response.json()
        )

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost
    | HTTPValidationError
]:
    """Export Skill

    Args:
        skill_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        skill_id=skill_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost
    | HTTPValidationError
    | None
):
    """Export Skill

    Args:
        skill_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost | HTTPValidationError
    """

    return sync_detailed(
        skill_id=skill_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost
    | HTTPValidationError
]:
    """Export Skill

    Args:
        skill_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        skill_id=skill_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost
    | HTTPValidationError
    | None
):
    """Export Skill

    Args:
        skill_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ExportSkillApiV1SkillsSkillIdExportPostResponseExportSkillApiV1SkillsSkillIdExportPost | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            skill_id=skill_id,
            client=client,
        )
    ).parsed
