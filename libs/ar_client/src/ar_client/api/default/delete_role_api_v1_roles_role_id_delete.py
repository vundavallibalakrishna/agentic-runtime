from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_role_api_v1_roles_role_id_delete_response_delete_role_api_v1_roles_role_id_delete import (
    DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    role_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/roles/{role_id}".format(
            role_id=quote(str(role_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = (
            DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete.from_dict(
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
    DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    role_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete | HTTPValidationError
]:
    """Delete Role

    Args:
        role_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        role_id=role_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    role_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete
    | HTTPValidationError
    | None
):
    """Delete Role

    Args:
        role_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete | HTTPValidationError
    """

    return sync_detailed(
        role_id=role_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    role_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete | HTTPValidationError
]:
    """Delete Role

    Args:
        role_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        role_id=role_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    role_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete
    | HTTPValidationError
    | None
):
    """Delete Role

    Args:
        role_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteRoleApiV1RolesRoleIdDeleteResponseDeleteRoleApiV1RolesRoleIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            role_id=role_id,
            client=client,
        )
    ).parsed
