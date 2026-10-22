from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.where_used_api_v1_skills_skill_id_where_used_get_response_where_used_api_v1_skills_skill_id_where_used_get import (
    WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    skill_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/skills/{skill_id}/where-used".format(
            skill_id=quote(str(skill_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet
    | None
):
    if response.status_code == 200:
        response_200 = WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet.from_dict(
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
    HTTPValidationError
    | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet
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
    HTTPValidationError
    | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet
]:
    """Where Used

    Args:
        skill_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet]
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
    HTTPValidationError
    | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet
    | None
):
    """Where Used

    Args:
        skill_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet
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
    HTTPValidationError
    | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet
]:
    """Where Used

    Args:
        skill_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet]
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
    HTTPValidationError
    | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet
    | None
):
    """Where Used

    Args:
        skill_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WhereUsedApiV1SkillsSkillIdWhereUsedGetResponseWhereUsedApiV1SkillsSkillIdWhereUsedGet
    """

    return (
        await asyncio_detailed(
            skill_id=skill_id,
            client=client,
        )
    ).parsed
