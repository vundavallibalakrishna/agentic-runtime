from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.delete_service_connection_api_v1_service_connections_connection_id_delete_response_delete_service_connection_api_v1_service_connections_connection_id_delete import (
    DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    connection_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/service-connections/{connection_id}".format(
            connection_id=quote(str(connection_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete.from_dict(
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
    DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete
    | HTTPValidationError
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete
    | HTTPValidationError
]:
    """Delete Service Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete
    | HTTPValidationError
    | None
):
    """Delete Service Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete | HTTPValidationError
    """

    return sync_detailed(
        connection_id=connection_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete
    | HTTPValidationError
]:
    """Delete Service Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        connection_id=connection_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    connection_id: UUID,
    *,
    client: AuthenticatedClient | Client,
) -> (
    DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete
    | HTTPValidationError
    | None
):
    """Delete Service Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDeleteResponseDeleteServiceConnectionApiV1ServiceConnectionsConnectionIdDelete | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            connection_id=connection_id,
            client=client,
        )
    ).parsed
