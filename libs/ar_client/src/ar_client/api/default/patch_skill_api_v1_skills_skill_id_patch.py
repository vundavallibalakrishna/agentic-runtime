from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.patch_skill_api_v1_skills_skill_id_patch_response_patch_skill_api_v1_skills_skill_id_patch import (
    PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch,
)
from ...models.skill_patch import SkillPatch
from typing import cast
from uuid import UUID


def _get_kwargs(
    skill_id: UUID,
    *,
    body: SkillPatch,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/skills/{skill_id}".format(
            skill_id=quote(str(skill_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch
    | None
):
    if response.status_code == 200:
        response_200 = (
            PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch.from_dict(
                response.json()
            )
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
    HTTPValidationError | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch
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
    body: SkillPatch,
) -> Response[
    HTTPValidationError | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch
]:
    """Patch Skill

    Args:
        skill_id (UUID):
        body (SkillPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch]
    """

    kwargs = _get_kwargs(
        skill_id=skill_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SkillPatch,
) -> (
    HTTPValidationError
    | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch
    | None
):
    """Patch Skill

    Args:
        skill_id (UUID):
        body (SkillPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch
    """

    return sync_detailed(
        skill_id=skill_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SkillPatch,
) -> Response[
    HTTPValidationError | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch
]:
    """Patch Skill

    Args:
        skill_id (UUID):
        body (SkillPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch]
    """

    kwargs = _get_kwargs(
        skill_id=skill_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    skill_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: SkillPatch,
) -> (
    HTTPValidationError
    | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch
    | None
):
    """Patch Skill

    Args:
        skill_id (UUID):
        body (SkillPatch):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PatchSkillApiV1SkillsSkillIdPatchResponsePatchSkillApiV1SkillsSkillIdPatch
    """

    return (
        await asyncio_detailed(
            skill_id=skill_id,
            client=client,
            body=body,
        )
    ).parsed
