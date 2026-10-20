from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_member_api_v1_groups_group_id_members_user_id_delete_response_delete_member_api_v1_groups_group_id_members_user_id_delete import DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID



def _get_kwargs(
    group_id: UUID,
    user_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/groups/{group_id}/members/{user_id}".format(group_id=quote(str(group_id), safe=""),user_id=quote(str(user_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    group_id: UUID,
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError]:
    """ Delete Member

    Args:
        group_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        group_id=group_id,
user_id=user_id,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    group_id: UUID,
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError | None:
    """ Delete Member

    Args:
        group_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError
     """


    return sync_detailed(
        group_id=group_id,
user_id=user_id,
client=client,

    ).parsed

async def asyncio_detailed(
    group_id: UUID,
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> Response[DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError]:
    """ Delete Member

    Args:
        group_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError]
     """


    kwargs = _get_kwargs(
        group_id=group_id,
user_id=user_id,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    group_id: UUID,
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,

) -> DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError | None:
    """ Delete Member

    Args:
        group_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteMemberApiV1GroupsGroupIdMembersUserIdDeleteResponseDeleteMemberApiV1GroupsGroupIdMembersUserIdDelete | HTTPValidationError
     """


    return (await asyncio_detailed(
        group_id=group_id,
user_id=user_id,
client=client,

    )).parsed
