from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.disconnect_api_v1_connections_grant_id_delete_response_disconnect_api_v1_connections_grant_id_delete import (
    DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    grant_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/connections/{grant_id}".format(
            grant_id=quote(str(grant_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete.from_dict(
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
    DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    grant_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete
    | HTTPValidationError
]:
    """Disconnect

    Args:
        grant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        grant_id=grant_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    grant_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete
    | HTTPValidationError
    | None
):
    """Disconnect

    Args:
        grant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete | HTTPValidationError
    """

    return sync_detailed(
        grant_id=grant_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    grant_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete
    | HTTPValidationError
]:
    """Disconnect

    Args:
        grant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        grant_id=grant_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    grant_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete
    | HTTPValidationError
    | None
):
    """Disconnect

    Args:
        grant_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DisconnectApiV1ConnectionsGrantIdDeleteResponseDisconnectApiV1ConnectionsGrantIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            grant_id=grant_id,
            client=client,
        )
    ).parsed
