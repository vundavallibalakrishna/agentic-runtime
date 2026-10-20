from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_team_api_v1_teams_team_id_delete_response_delete_team_api_v1_teams_team_id_delete import DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    team_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/teams/{team_id}".format(team_id=quote(str(team_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError]:
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

) -> Response[DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError]:
    """ Delete Team

    Args:
        team_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError]
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

) -> DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError | None:
    """ Delete Team

    Args:
        team_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError
     """


    return sync_detailed(
        team_id=team_id,
client=client,

    ).parsed

async def asyncio_detailed(
    team_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError]:
    """ Delete Team

    Args:
        team_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        team_id=team_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    team_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError | None:
    """ Delete Team

    Args:
        team_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteTeamApiV1TeamsTeamIdDeleteResponseDeleteTeamApiV1TeamsTeamIdDelete | HTTPValidationError
     """


    return (await asyncio_detailed(
        team_id=team_id,
client=client,

    )).parsed
