from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.put_user_scim_v2_users_user_id_put_body import PutUserScimV2UsersUserIdPutBody
from ...models.put_user_scim_v2_users_user_id_put_response_put_user_scim_v2_users_user_id_put import PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut
from typing import cast
from uuid import UUID



def _get_kwargs(
    user_id: UUID,
    *,
    body: PutUserScimV2UsersUserIdPutBody,

) -> dict[str, Any]:
    headers: dict[str, Any] = {}


    

    

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/scim/v2/Users/{user_id}".format(user_id=quote(str(user_id), safe=""),),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs



def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut | None:
    if response.status_code == 200:
        response_200 = PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut.from_dict(response.json())



        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())



        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PutUserScimV2UsersUserIdPutBody,

) -> Response[HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut]:
    """ Put User

    Args:
        user_id (UUID):
        body (PutUserScimV2UsersUserIdPutBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut]
     """


    kwargs = _get_kwargs(
        user_id=user_id,
body=body,

    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)

def sync(
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PutUserScimV2UsersUserIdPutBody,

) -> HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut | None:
    """ Put User

    Args:
        user_id (UUID):
        body (PutUserScimV2UsersUserIdPutBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut
     """


    return sync_detailed(
        user_id=user_id,
client=client,
body=body,

    ).parsed

async def asyncio_detailed(
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PutUserScimV2UsersUserIdPutBody,

) -> Response[HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut]:
    """ Put User

    Args:
        user_id (UUID):
        body (PutUserScimV2UsersUserIdPutBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut]
     """


    kwargs = _get_kwargs(
        user_id=user_id,
body=body,

    )

    response = await client.get_async_httpx_client().request(
        **kwargs
    )

    return _build_response(client=client, response=response)

async def asyncio(
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
    body: PutUserScimV2UsersUserIdPutBody,

) -> HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut | None:
    """ Put User

    Args:
        user_id (UUID):
        body (PutUserScimV2UsersUserIdPutBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | PutUserScimV2UsersUserIdPutResponsePutUserScimV2UsersUserIdPut
     """


    return (await asyncio_detailed(
        user_id=user_id,
client=client,
body=body,

    )).parsed
