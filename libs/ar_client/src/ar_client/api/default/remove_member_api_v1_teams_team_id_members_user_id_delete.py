from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.remove_member_api_v1_teams_team_id_members_user_id_delete_response_remove_member_api_v1_teams_team_id_members_user_id_delete import (
    RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete,
)
from typing import cast
from uuid import UUID


def _get_kwargs(
    team_id: UUID,
    user_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/teams/{team_id}/members/{user_id}".format(
            team_id=quote(str(team_id), safe=""),
            user_id=quote(str(user_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    HTTPValidationError
    | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete
    | None
):
    if response.status_code == 200:
        response_200 = RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete.from_dict(
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
    | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    team_id: UUID,
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete
]:
    """Remove Member

    Args:
        team_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete]
    """

    kwargs = _get_kwargs(
        team_id=team_id,
        user_id=user_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    team_id: UUID,
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete
    | None
):
    """Remove Member

    Args:
        team_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete
    """

    return sync_detailed(
        team_id=team_id,
        user_id=user_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    team_id: UUID,
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    HTTPValidationError
    | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete
]:
    """Remove Member

    Args:
        team_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete]
    """

    kwargs = _get_kwargs(
        team_id=team_id,
        user_id=user_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    team_id: UUID,
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    HTTPValidationError
    | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete
    | None
):
    """Remove Member

    Args:
        team_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RemoveMemberApiV1TeamsTeamIdMembersUserIdDeleteResponseRemoveMemberApiV1TeamsTeamIdMembersUserIdDelete
    """

    return (
        await asyncio_detailed(
            team_id=team_id,
            user_id=user_id,
            client=client,
        )
    ).parsed
