from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_team_api_v1_teams_team_id_get_response_get_team_api_v1_teams_team_id_get import (
    GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    team_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/teams/{team_id}".format(
            team_id=quote(str(team_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet.from_dict(
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
) -> Response[GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    team_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError]:
    """Get Team

    Args:
        team_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        team_id=team_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    team_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError | None:
    """Get Team

    Args:
        team_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError
    """

    return sync_detailed(
        team_id=team_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    team_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError]:
    """Get Team

    Args:
        team_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        team_id=team_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    team_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError | None:
    """Get Team

    Args:
        team_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetTeamApiV1TeamsTeamIdGetResponseGetTeamApiV1TeamsTeamIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            team_id=team_id,
            client=client,
        )
    ).parsed
