from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.put_member_api_v1_groups_group_id_members_user_id_put_response_put_member_api_v1_groups_group_id_members_user_id_put import PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut
from typing import cast
from uuid import UUID



def _get_kwargs(
    group_id: UUID,
    user_id: UUID,

) -> dict[str, Any]:
    

    

    

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/api/v1/groups/{group_id}/members/{user_id}".format(group_id=quote(str(group_id), safe=""),user_id=quote(str(user_id), safe=""),),
    }


    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut | None:
    if response.status_code == 200:
        response_200 = PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut]:
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

) -> Response[HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut]:
    """ Put Member

    Args:
        group_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut]
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

) -> HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut | None:
    """ Put Member

    Args:
        group_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut
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

) -> Response[HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut]:
    """ Put Member

    Args:
        group_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut]
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

) -> HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut | None:
    """ Put Member

    Args:
        group_id (UUID):
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PutMemberApiV1GroupsGroupIdMembersUserIdPutResponsePutMemberApiV1GroupsGroupIdMembersUserIdPut
     """


    return (await asyncio_detailed(
        group_id=group_id,
user_id=user_id,
client=client,

    )).parsed
