from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.get_service_connection_api_v1_service_connections_connection_id_get_response_get_service_connection_api_v1_service_connections_connection_id_get import (
    GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet,
)
from ...models.http_validation_error import HTTPValidationError
from typing import cast
from uuid import UUID


def _get_kwargs(
    connection_id: UUID,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/service-connections/{connection_id}".format(
            connection_id=quote(str(connection_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet
    | HTTPValidationError
    | None
):
    if response.status_code == 200:
        response_200 = GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet.from_dict(
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
    GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet
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
    GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet
    | HTTPValidationError
]:
    """Get Service Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet | HTTPValidationError]
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
    GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet
    | HTTPValidationError
    | None
):
    """Get Service Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet | HTTPValidationError
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
    GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet
    | HTTPValidationError
]:
    """Get Service Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet | HTTPValidationError]
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
    GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet
    | HTTPValidationError
    | None
):
    """Get Service Connection

    Args:
        connection_id (UUID):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetServiceConnectionApiV1ServiceConnectionsConnectionIdGetResponseGetServiceConnectionApiV1ServiceConnectionsConnectionIdGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            connection_id=connection_id,
            client=client,
        )
    ).parsed
