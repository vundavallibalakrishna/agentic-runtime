from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.list_skills_api_v1_skills_get_response_list_skills_api_v1_skills_get import (
    ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet,
)
from ...types import UNSET, Unset
from typing import cast
from uuid import UUID


def _get_kwargs(
    *,
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    team_id: None | Unset | UUID = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["q"] = q

    params["status"] = status

    params["owner"] = owner

    json_team_id: None | str | Unset
    if isinstance(team_id, Unset):
        json_team_id = UNSET
    elif isinstance(team_id, UUID):
        json_team_id = str(team_id)
    else:
        json_team_id = team_id
    params["team_id"] = json_team_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/skills",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet | None:
    if response.status_code == 200:
        response_200 = ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet.from_dict(
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
) -> Response[HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    team_id: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet]:
    """List Skills

    Args:
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        owner (str | Unset):  Default: ''.
        team_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet]
    """

    kwargs = _get_kwargs(
        q=q,
        status=status,
        owner=owner,
        team_id=team_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    team_id: None | Unset | UUID = UNSET,
) -> HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet | None:
    """List Skills

    Args:
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        owner (str | Unset):  Default: ''.
        team_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet
    """

    return sync_detailed(
        client=client,
        q=q,
        status=status,
        owner=owner,
        team_id=team_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    team_id: None | Unset | UUID = UNSET,
) -> Response[HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet]:
    """List Skills

    Args:
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        owner (str | Unset):  Default: ''.
        team_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet]
    """

    kwargs = _get_kwargs(
        q=q,
        status=status,
        owner=owner,
        team_id=team_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: str | Unset = "",
    status: str | Unset = "",
    owner: str | Unset = "",
    team_id: None | Unset | UUID = UNSET,
) -> HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet | None:
    """List Skills

    Args:
        q (str | Unset):  Default: ''.
        status (str | Unset):  Default: ''.
        owner (str | Unset):  Default: ''.
        team_id (None | Unset | UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ListSkillsApiV1SkillsGetResponseListSkillsApiV1SkillsGet
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            status=status,
            owner=owner,
            team_id=team_id,
        )
    ).parsed
