from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_user_scim_v2_users_user_id_delete_response_delete_user_scim_v2_users_user_id_delete import (
    DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    user_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/scim/v2/Users/{user_id}".format(
            user_id=quote(str(user_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete.from_dict(
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
    DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete | HTTPValidationError
]:
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
) -> Response[
    DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete | HTTPValidationError
]:
    """Delete User

    Args:
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete
    | HTTPValidationError
    | None
):
    """Delete User

    Args:
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete | HTTPValidationError
    """

    return sync_detailed(
        user_id=user_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete | HTTPValidationError
]:
    """Delete User

    Args:
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    user_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete
    | HTTPValidationError
    | None
):
    """Delete User

    Args:
        user_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteUserScimV2UsersUserIdDeleteResponseDeleteUserScimV2UsersUserIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            user_id=user_id,
            client=client,
        )
    ).parsed
