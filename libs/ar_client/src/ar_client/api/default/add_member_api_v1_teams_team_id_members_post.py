from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.add_member_api_v1_teams_team_id_members_post_response_add_member_api_v1_teams_team_id_members_post import AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost
from ...models.http_validation_error import HTTPValidationError
from ...models.team_member_create import TeamMemberCreate
from typing import cast
from uuid import UUID



def _get_kwargs(
    team_id: UUID,
    *,
    body: TeamMemberCreate,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/teams/{team_id}/members".format(team_id=quote(str(team_id), safe=""),),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError]:
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
    body: TeamMemberCreate,

) -> Response[AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError]:
    """ Add Member

    Args:
        team_id (UUID):
        body (TeamMemberCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        team_id=team_id,
body=body,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    team_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TeamMemberCreate,

) -> AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError | None:
    """ Add Member

    Args:
        team_id (UUID):
        body (TeamMemberCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError
     """


    return sync_detailed(
        team_id=team_id,
client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    team_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TeamMemberCreate,

) -> Response[AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError]:
    """ Add Member

    Args:
        team_id (UUID):
        body (TeamMemberCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        team_id=team_id,
body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    team_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: TeamMemberCreate,

) -> AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError | None:
    """ Add Member

    Args:
        team_id (UUID):
        body (TeamMemberCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddMemberApiV1TeamsTeamIdMembersPostResponseAddMemberApiV1TeamsTeamIdMembersPost | HTTPValidationError
     """


    return (await asyncio_detailed(
        team_id=team_id,
client=client,
body=body,

    )).parsed
